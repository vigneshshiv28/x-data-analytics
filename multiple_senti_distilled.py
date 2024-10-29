
import streamlit as st
import pandas as pd
import plotly.express as px
from transformers import pipeline

# Title of the app
st.title('Multilingual Tweet Sentiment Analysis for Multiple Accounts')

st.markdown('''This application allows you to analyze tweets from multiple accounts,
including performing sentiment analysis to understand user sentiments in multiple languages.''')

# Sidebar description
st.sidebar.title("Multilingual Tweet Sentiment Analysis")
st.sidebar.markdown("This application performs sentiment analysis on multilingual tweets from various accounts.")

# Load datasets for all four accounts
account_files = {
    'Home Credit': 'c:/Users/Khyati/Downloads/adjusted_refined_Homecredit_data.csv',
    'Fibe India': "C:/Users/Khyati/Downloads/fibeIndia_cleaned_tweets.csv",
    'Cashe App': "C:/Users/Khyati/Downloads/casheapp_cleaned_tweets.csv",
    'Kreditbee': "C:/Users/Khyati/Downloads/refined_kreditbee_data.csv"
}

# Read datasets
account_data = {}
for account, file_path in account_files.items():
    account_data[account] = pd.read_csv(file_path)

# Initialize the multilingual sentiment analysis pipeline
sentiment_pipeline = pipeline("text-classification", model="lxyuan/distilbert-base-multilingual-cased-sentiments-student")

# Function to classify sentiment using the pre-trained model
def get_sentiment(text):
    result = sentiment_pipeline(text)[0]
    return result['label'], result['score']

# Apply sentiment analysis to all datasets
for account in account_data:
    account_data[account] = account_data[account][account_data[account]['text'].apply(lambda x: isinstance(x, str))]
    sentiments = account_data[account]['text'].apply(get_sentiment)
    account_data[account]['sentiment'] = sentiments.apply(lambda x: x[0])
    account_data[account]['sentiment_score'] = sentiments.apply(lambda x: x[1])

# Display data for each account
if st.checkbox("Show Data"):
    selected_account = st.selectbox("Select Account", list(account_data.keys()))
    st.write(account_data[selected_account].head(50))

# Sidebar for tweet filtering options
st.sidebar.subheader('Tweets Analyzer')
sentiment_choice = st.sidebar.radio('Sentiment Type', ('POSITIVE', 'NEGATIVE', 'NEUTRAL'))

# if not filtered_data.empty:
#     st.write(f"Random {sentiment_choice} tweet from {selected_account}:")
#     st.write(filtered_data[['text']].sample(1).iat[0, 0])
# else:
#     st.write(f"No {sentiment_choice} tweets found in {selected_account}.")

# Visualization Options
st.sidebar.subheader('Visualization of Tweets')
select = st.sidebar.selectbox('Visualization of Tweets', ['Histogram', 'Pie Chart'], key='visualization')

# Counting the number of tweets by sentiment for each account
sentiment_counts = {}
for account in account_data:
    sentiment_count = account_data[account]['sentiment'].value_counts()
    sentiment_counts[account] = pd.DataFrame({'Sentiment': sentiment_count.index, 'Tweets': sentiment_count.values})

# Plot sentiment counts for all accounts
if select == "Histogram":
    for account, df in sentiment_counts.items():
        st.markdown(f"### Tweet count by sentiment for {account}")
        fig = px.bar(df, x='Sentiment', y='Tweets', color='Tweets', height=500, title=f'{account} Sentiment Counts')
        st.plotly_chart(fig)
else:
    for account, df in sentiment_counts.items():
        st.markdown(f"### Tweet count by sentiment for {account}")
        fig = px.pie(df, values='Tweets', names='Sentiment', title=f'{account} Sentiment Distribution')
        st.plotly_chart(fig)

# Overall Sentiment Analysis
overall_sentiment = pd.concat([df.assign(Account=account) for account, df in account_data.items()])
overall_sentiment_summary = overall_sentiment.groupby(['Account', 'sentiment']).size().reset_index(name='Tweets')

st.markdown("### Overall Sentiment Analysis Across All Accounts")
fig = px.bar(overall_sentiment_summary, x='Account', y='Tweets', color='sentiment', barmode='group', height=500)
st.plotly_chart(fig)

# Calculate overall sentiment scores for each account
overall_scores = {}
for account in account_data:
    total_score = account_data[account]['sentiment_score'].sum()
    tweet_count = len(account_data[account])
    overall_scores[account] = total_score / tweet_count

# Rank the accounts based on overall sentiment scores
ranked_accounts = sorted(overall_scores.items(), key=lambda x: x[1], reverse=True)

st.markdown("### Ranking of Accounts Based on Overall Sentiment Score")
ranked_df = pd.DataFrame(ranked_accounts, columns=['Account', 'Overall Sentiment Score'])
st.write(ranked_df)

# Tweet time analysis
st.sidebar.subheader('Time & Location of Tweets')
hr = st.sidebar.slider("Hour of the day", 0, 23)
for account in account_data:
    account_data[account]['Date'] = pd.to_datetime(account_data[account]['timestamp'])
    hr_data = account_data[account][account_data[account]['Date'].dt.hour == hr]
    if not st.sidebar.checkbox(f"Hide {account} Tweets", True, key=f'hide_{account}'):
        st.markdown(f"### Location of the {account} tweets based on the hour of the day")
        st.markdown(f"{len(hr_data)} tweets during {hr}:00 and {hr+1}:00")
        st.map(hr_data[['latitude', 'longitude']].dropna())

# Tweets by author filter
st.sidebar.subheader("Tweets by Author")
for account in account_data:
    author_filter = st.sidebar.multiselect(f"Select Authors for {account}", account_data[account]['author_name'].dropna().unique(), key=f'author_{account}')
    if len(author_filter) > 0:
        filtered_data = account_data[account][account_data[account]['author_name'].isin(author_filter)]
        fig = px.histogram(filtered_data, x='author_name', y='sentiment', histfunc='count', color='sentiment', title=f'{account} Tweets by Author')
        st.plotly_chart(fig)