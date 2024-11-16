import streamlit as st
import pandas as pd
import plotly.express as px

# Title of the app
st.title('Multilingual Tweet Sentiment and Topic Analysis for Multiple Accounts')

st.markdown('''This application allows you to analyze tweets from multiple accounts,
including performing sentiment and topic analysis to understand user feedback in multiple languages.''')

# Sidebar setup for account selection
st.sidebar.title("Select Account")
account = st.sidebar.selectbox("Choose an account to analyze", ["Cashe App", "Fibe India", "Home Credit", "Kreditbee"])

# Map each account to its corresponding CSV file
account_files = {
    'Home Credit': 'final_tweets/HomeCredit.csv',
    'Fibe India': "final_tweets/Fibe.csv",
    'Cashe App': 'final_tweets/CasheApp.csv',
    'Kreditbee': 'final_tweets/KreditBee.csv'
}

# Function to load and preprocess data
@st.cache_data  # Cache the data loading to improve performance
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        # Add sentiment score mapping
        sentiment_map = {'positive': 5, 'neutral': 2.5, 'negative': 0}
        df['score'] = df['sentiment'].map(sentiment_map)
        return df
    except Exception as e:
        st.error(f"Error loading data from {file_path}: {str(e)}")
        return None

# Load all datasets at startup for ranking
all_account_data = {}
overall_scores = {}

for acc, file_path in account_files.items():
    df = load_data(file_path)
    if df is not None:
        all_account_data[acc] = df
        overall_scores[acc] = df['score'].mean()

# Display rankings
ranked_df = pd.DataFrame(overall_scores.items(), columns=['Account', 'Overall Sentiment Score'])
ranked_df = ranked_df.sort_values('Overall Sentiment Score', ascending=False)

st.markdown("### Ranking of Accounts Based on Overall Sentiment Score")
st.write(ranked_df)

# Display ranking visualization
fig = px.bar(ranked_df, x='Account', y='Overall Sentiment Score', color='Overall Sentiment Score',
             title="Overall Sentiment Score by Account", range_y=[0, 5])
st.plotly_chart(fig)

# Load data for selected account
tweet_data = all_account_data.get(account)

if tweet_data is None:
    st.error(f"Could not load data for {account}")
    st.stop()

# Display dataset information
if st.checkbox("Show Raw Data"):
    st.write(tweet_data.head(50))

# Main analysis selection
analysis_type = st.sidebar.radio("Choose Analysis Type", ["Sentiment Analysis", "Topic Analysis"])

# Sentiment Analysis
if analysis_type == "Sentiment Analysis":
    st.header("Sentiment Analysis")

    # Sidebar options for sentiment filtering
    st.sidebar.subheader('Filter by Sentiment')
    sentiment_choice = st.sidebar.radio('Sentiment Type', ('positive', 'negative', 'neutral'))
    filtered_data = tweet_data[tweet_data['sentiment'] == sentiment_choice]

    st.write(f"### Sample {sentiment_choice} Tweets from {account}")
    st.write(filtered_data[['author_name', 'text', 'timestamp']].head(10))

    # Visualization options
    st.sidebar.subheader('Sentiment Visualization')
    sentiment_visualization = st.sidebar.selectbox("Select Visualization", ["Histogram", "Pie Chart"])

    sentiment_counts = tweet_data['sentiment'].value_counts().reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']

    if sentiment_visualization == "Histogram":
        fig = px.bar(sentiment_counts, x='Sentiment', y='Count', color='Count',
                    title=f'Sentiment Distribution for {account}')
    else:
        fig = px.pie(sentiment_counts, names='Sentiment', values='Count',
                    title=f'Sentiment Distribution for {account}')
    st.plotly_chart(fig)

# Topic Analysis
elif analysis_type == "Topic Analysis":
    st.header("Topic Analysis")

    topics = sorted(tweet_data['topics'].unique())
    
    st.sidebar.subheader('Filter by Topic')
    selected_topic = st.sidebar.selectbox("Select Topic", topics)
    topic_filtered_data = tweet_data[tweet_data['topics'] == selected_topic]

    st.write(f"### Tweets on the Topic: {selected_topic} for {account}")
    st.write(topic_filtered_data[['author_name', 'text', 'timestamp']].head(10))

    st.sidebar.subheader("Topic Visualization")
    topic_visualization = st.sidebar.selectbox("Select Visualization Type", ["Bar Chart", "Pie Chart"])

    topic_counts = tweet_data['topics'].value_counts().reset_index()
    topic_counts.columns = ['Topic', 'Count']

    if topic_visualization == "Bar Chart":
        fig = px.bar(topic_counts, x='Topic', y='Count', color='Count',
                    title=f'Topic Frequency for {account}')
    else:
        fig = px.pie(topic_counts, names='Topic', values='Count',
                    title=f'Topic Distribution for {account}')
    st.plotly_chart(fig)

# Monthly Trends
st.header("Monthly Trends")

try:
    # Convert timestamp to datetime
    tweet_data['year_month'] = pd.to_datetime(tweet_data['timestamp']).dt.to_period('M').dt.to_timestamp()

    # Monthly sentiment trends
    monthly_sentiment_counts = (tweet_data.groupby(['year_month', 'sentiment'])
                              .size()
                              .reset_index(name='count'))
    
    fig_sentiment = px.line(monthly_sentiment_counts, 
                          x='year_month', 
                          y='count',
                          color='sentiment',
                          title=f"Sentiment Trends Over Time for {account}")
    
    fig_sentiment.update_layout(
        xaxis_title="Date",
        yaxis_title="Number of Tweets",
        legend_title="Sentiment"
    )
    st.plotly_chart(fig_sentiment)

    # Monthly topic trends
    monthly_topic_counts = (tweet_data.groupby(['year_month', 'topics'])
                          .size()
                          .reset_index(name='count'))
    
    fig_topic = px.line(monthly_topic_counts, 
                       x='year_month', 
                       y='count',
                       color='topics',
                       title=f"Topic Trends Over Time for {account}")
    
    fig_topic.update_layout(
        xaxis_title="Date",
        yaxis_title="Number of Tweets",
        legend_title="Topics"
    )
    st.plotly_chart(fig_topic)

except Exception as e:
    st.error(f"Error creating trends: {str(e)}")