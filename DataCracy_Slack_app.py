import pandas as pd
import seaborn as sns
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import json
import requests
import sys
import os
import re
from datetime import datetime as dt
import matplotlib.image as mpimg
import math
from boto.s3.connection import S3Connection


s3 = S3Connection( os.environ['TEST'])

SLACK_BEARER_TOKEN = s3



@st.cache
def load_users_df():
    # Slack API User Data
    endpoint = "https://slack.com/api/users.list"
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    response_json = requests.post(endpoint, headers=headers).json()
    user_dat = response_json['members']

    # Convert to CSV
    user_dict = {'user_id':[],'name':[],'display_name':[],'real_name':[],'title':[],'is_bot':[]}
    for i in range(len(user_dat)):
      user_dict['user_id'].append(user_dat[i]['id'])
      user_dict['name'].append(user_dat[i]['name'])
      user_dict['display_name'].append(user_dat[i]['profile']['display_name'])
      user_dict['real_name'].append(user_dat[i]['profile']['real_name_normalized'])
      user_dict['title'].append(user_dat[i]['profile']['title'])
      user_dict['is_bot'].append(int(user_dat[i]['is_bot']))
    user_df = pd.DataFrame(user_dict)
    # Read dtc_group hosted in github
    dtc_groups = pd.read_csv(DTC_GROUPS_URL)
    user_df = user_df.merge(dtc_groups, how='left', on='name')
    return user_df

user_df = load_users_df()
st.write(user_df)


img1 = mpimg.imread('DataCracy.png')
st.image(img1, width = 500)

st.write("""
# Welcome to Dashboard of DataCracy 

### Made by : **Nguyễn Trần Quân**. 
You can come across him at [Quan Nguyen](https://github.com/Quan030994/atom-assignments)

""")

def process_msg_data(msg_df, user_df, channel_df):
    ## Extract 2 reply_users
    msg_df['reply_user1'] = msg_df['reply_users'].apply(lambda x: x[0] if x != 0 else '')
    msg_df['reply_user2'] = msg_df['reply_users'].apply(lambda x: x[1] if x != 0 and len(x) > 1 else '')
    ## Merge to have a nice name displayed
    msg_df = msg_df.merge(user_df[['user_id','name','DataCracy_role']].rename(columns={'name':'submit_name'}), \
        how='left',on='user_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply1_name','user_id':'reply1_id'}), \
        how='left', left_on='reply_user1', right_on='reply1_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply2_name','user_id':'reply2_id'}), \
        how='left', left_on='reply_user2', right_on='reply2_id')
    ## Merge for nice channel name
    msg_df = msg_df.merge(channel_df[['channel_id','channel_name','created_at']], how='left',on='channel_id')
    ## Format datetime cols
    # msg_df['created_at'] = msg_df['created_at'].dt.strftime('%Y-%m-%d')
    # msg_df['msg_date'] = msg_df['msg_ts'].dt.strftime('%Y-%m-%d')
    # msg_df['msg_time'] = msg_df['msg_ts'].dt.strftime('%H:%M')
    msg_df['created_at'] = pd.to_datetime(msg_df['created_at'])
    msg_df['msg_date'] = pd.to_datetime(msg_df['msg_ts'])
    msg_df['msg_ts'] = pd.to_datetime(msg_df['msg_ts'])
    msg_df['dayofweek_msg'] = msg_df['msg_ts'].dt.dayofweek
    msg_df['hour_msg'] = msg_df['msg_ts'].dt.hour
    msg_df['wordcount'] = msg_df.text.apply(lambda s: len(s.split()))
    return msg_df



# Table data
user_df = pd.read_csv('user_df.csv')
channel_df = pd.read_csv('channel_df.csv')
msg_df = pd.read_csv('msg_df.csv')

channel_df['created_at'] = pd.to_datetime(channel_df['created_at'])

# Process data
msg_process_df = process_msg_data(msg_df, user_df, channel_df)



# Number of assignments submitted
submit_df = msg_process_df[((msg_process_df.github_link.notnull() & msg_process_df.channel_name != 'atom-assignment1'))\
                            & msg_process_df.DataCracy_role.str.contains('Learner')\
                            & msg_process_df.channel_name.str.contains('assignment')]

last_submit_df = submit_df.groupby(['channel_name','user_id']).msg_date.idxmax()



submit_df['be_reviewed'] = submit_df[['reply1_id','reply2_id','user_id','reply_user_count']].apply(lambda x: (0,1) \
                                        [(x['reply_user_count'] > 0) & ((x['reply1_id'] != x['user_id']) | (x['reply2_id'] != x['user_id'])\
                                        | ((x['reply1_id'] != x['user_id']) & (x['reply2_id'] != x['user_id'])))], axis=1)


submit_df['dayofweek'] =submit_df.dayofweek_msg.apply(lambda x :  "Mon" if x == 0 else
                                                             "Tue" if x ==1 else
                                                             "Wed" if x ==2 else
                                                             "Thu" if x == 3 else
                                                             "Fri" if x == 4 else
                                                             "Sat" if x == 5 else
                                                             "Sun"
                                                            )



submit_df['weekend'] = submit_df["dayofweek"].apply(lambda x : 1 if x == 'Sun' or x == 'Sat' else 0)

submit_df["timepoint_of_the_day"] = submit_df.hour_msg.apply(lambda x :
                                                             "late night" if x < 4 else
                                                             "early morning" if x < 7 else
                                                             "morning" if x < 11 else
                                                             "early afternoon" if x < 16 else
                                                             "afternoon" if x < 18 else
                                                             "evening"
                                                            )




learner_stat = submit_df.loc[last_submit_df].groupby(['submit_name','DataCracy_role']).agg({ 'channel_name': 'count' ,
                                                                  'be_reviewed': 'sum',
                                                                  'wordcount': 'sum'})


learner_stat = learner_stat.reset_index()
learner_stat = learner_stat.rename(columns={'channel_name':'submitted'})
learner_stat['rate_be_reviewed'] = round(learner_stat['be_reviewed'] * 100 / learner_stat['submitted'],2)
learner_stat = learner_stat.drop(['DataCracy_role'], axis = 1)
learner_stat = pd.merge(user_df[user_df.DataCracy_role.notnull() & user_df.DataCracy_role.str.contains('Learner')][['user_id','name','DataCracy_role']], learner_stat, how= 'left', left_on='name', right_on='submit_name')
learner_stat = learner_stat.drop('submit_name', axis= 1)
learner_stat = learner_stat.fillna(0)

st.markdown('### Below is information about the students assignments at **{}**'\
            .format(channel_df[channel_df.channel_name.str.contains('atom-week')].loc[channel_df.created_at.idxmax()]['channel_name']))
st.write("""
#### Data Fields:
1. User_id: User ID when logging into the DataCracy workspace. This is a key that unique.
2. Name: The name of when logging into the DataCracy workspace.
3. DataCracy_role: The user's role when participating in class.
4. Submitted: The number of assignments was submitted successfully.
5. Be_Reviewd: The number of assignments was submitted successfully and be reviewed.
6. Workcount: The number of words that the User discussed in the channel of Group.
7. Rate_be_reviewd: The ratio of the number of assignments is reviewed divided by the number of assignments be submitted.


## **Key Performance Indicator**
""")

def make_plot(df, grouper, col='', title='', palette='', loc_lengend = 'upper right'):
    g = sns.countplot(x=col, hue=grouper, data=df#, palette=palette
                      )
    g.set_xticklabels(labels=df[col].unique(), rotation=0, ha='center')
    g.set_ylabel("Number")
    g.set_title(title)
    g.legend(frameon=False,loc=loc_lengend)
    sns.set_style({"axes.facecolor": "white"})
    ##adding annotations
    total_counts_dict = dict(df[grouper].value_counts().sort_index())
    plot_dict = {}

    for i in df[col].unique():
        val_counts = dict(df.loc[df[col] == i, grouper].value_counts())
        for k, v in val_counts.items():
            if k not in plot_dict:
                plot_dict[val_counts[k]] = val_counts[k]
            else:
                plot_dict[0] = 0
    for p in g.patches:
        height = p.get_height()
        if math.isnan(height):
            continue
        g.text(p.get_x() + p.get_width() / 2.0,
               height + 0.5,
               f"{plot_dict[height]:.0f}", ha="center", va="bottom", fontsize=8, weight="semibold", size="large")


st.set_option('deprecation.showPyplotGlobalUse', False)
col1 = st.sidebar
choose_type = col1.selectbox('Type of Data',['Learner','Assignment'])

if choose_type == 'Learner':
    st.write("""

    ### **Learner**


    #### Detail
    """
             )

    st.write(learner_stat)

    st.write("""

    #### Chart

    ##### **The Assignment submitted and be reviewed**

    """)

    st.markdown("***")

    sns.set(style='darkgrid', font_scale=1.0, rc={"figure.figsize": [14, 6]})
    f, ax = plt.subplots(1, 2, figsize=(14, 6))
    g = sns.countplot(x='submitted', data=learner_stat, ax=ax[0])
    ax[0].set_title('Distribution of the number of assignment submitted')
    ax[0].set_ylabel('Number')
    ax[0].set_xlabel('The number of assignment submitted')
    plot_dict = {}
    val_counts = dict(learner_stat.submitted.value_counts().sort_index())
    for k, v in val_counts.items():
        if k in val_counts:
            plot_dict[val_counts[k]] = val_counts[k]
        else:
            plot_dict[0] = 0
    for x in g.patches:
        height = x.get_height()
        g.text(x.get_x() + x.get_width() / 2.0, height, plot_dict[height] \
               , ha="center", va="bottom", fontsize=8, weight="semibold", size="large")

    h = sns.countplot(x='be_reviewed', data=learner_stat, ax=ax[1])
    ax[1].set_title('Distribution of the number of assignment submitted and be reviewed')
    ax[1].set_ylabel('Number')
    ax[1].set_xlabel('The number of assignment submitted and be reviewed')
    plot_dict = {}
    val_counts = dict(learner_stat.be_reviewed.value_counts().sort_index())
    for k, v in val_counts.items():
        if k in val_counts:
            plot_dict[val_counts[k]] = val_counts[k]
        else:
            plot_dict[0] = 0
    for x in h.patches:
        height = x.get_height()
        h.text(x.get_x() + x.get_width() / 2.0, height, plot_dict[height], ha="center", va="bottom", fontsize=8,
               weight="semibold", size="large")
    st.pyplot()

    st.write("""

    ##### **The distribution between be reviewed and Group Learner**

    """)

    st.markdown("***")

    sns.set(style='darkgrid', font_scale=1.0, rc={"figure.figsize": [14, 6]})
    f, ax = plt.subplots(1, 2)
    labels = ['Learner_Gr1', 'Learner_Gr2', 'Learner_Gr3', 'Learner_Gr4']
    colors = ['lightskyblue', 'red', 'blue', 'green']
    explode = (0, 0.1, 0, 0.1)
    learner_stat['DataCracy_role'].value_counts().sort_index().plot.pie(explode=[0, 0.1, 0, 0.1], autopct='%1.1f%%',
                                                                        ax=ax[0], shadow=True, colors=colors)
    ax[0].set_title('The Ratio of Group')
    ax[0].set_ylabel('')
    ax[0].legend(labels, loc='upper right')
    sns.countplot(x='rate_be_reviewed', hue='DataCracy_role', data=learner_stat)
    plt.title('The distribution be reviewd between group learner')
    ax[1].legend(labels, loc='upper left')
    # make_plot(learner_stat, grouper='DataCracy_role',col='rate_be_reviewed'\
    #           ,title='The distribution be reviewd between group learner', loc_lengend='upper left')
    st.pyplot()

    st.write("""

    ##### **The distribution of word count**

    """)

    st.markdown("***")

    sns.set(style='darkgrid', font_scale=1.0, rc={"figure.figsize": [14, 6]})
    sns.distplot(learner_stat['wordcount'], bins=learner_stat.shape[0], kde=False, norm_hist=False, color="red") \
        .set(xlabel='Word Count', ylabel='Count')
    st.pyplot()
else:

    st.write("""
    ### **Assignment**


    #### Chart


    ##### **The distribution between submitted and Assignment**

    """)

    st.markdown("***")

    sns.set(style='darkgrid', font_scale=1.5, rc={"figure.figsize": [14, 6]})
    sns.countplot(x='dayofweek', hue='channel_name', data=submit_df.loc[last_submit_df])
    plt.title('The distribution submitted of the assignment between the days of the week')
    st.pyplot()

    st.markdown("***")

    sns.set(style='darkgrid', font_scale=1.5, rc={"figure.figsize": [14, 6]})
    sns.countplot(x='timepoint_of_the_day', hue='channel_name', data=submit_df.loc[last_submit_df])
    plt.title('The distribution submitted of the assignment at the time points of the day')
    plt.legend(loc='upper right')
    st.pyplot()




