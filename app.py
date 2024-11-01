import streamlit as st
import pandas as pd
import plotly.express as px
from transformers import pipeline

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



# Define a function to calculate the overall sentiment score for an account
def calculate_overall_sentiment_score(df):
    total_score = df['score'].sum()  # Sum of sentiment scores
    tweet_count = len(df)  # Total number of tweets
    return total_score / tweet_count if tweet_count > 0 else 0  # Average score

# Calculate overall sentiment scores for each account
overall_scores = {}
for account, file_path in account_files.items():
    df = pd.read_csv(file_path)
    # Assuming sentiment_score column exists; if not, create it based on sentiment mapping
    sentiment_map = {'positive': 5, 'neutral': 2.5, 'negative': 0}
    df['score'] = df['sentiment'].map(sentiment_map)
    overall_scores[account] = calculate_overall_sentiment_score(df)

# Rank the accounts based on overall sentiment scores
ranked_accounts = sorted(overall_scores.items(), key=lambda x: x[1], reverse=True)

# Convert the ranked accounts into a DataFrame for display
ranked_df = pd.DataFrame(ranked_accounts, columns=['Account', 'Overall Sentiment Score'])

# Display the ranking table
st.markdown("### Ranking of Accounts Based on Overall Sentiment Score")
st.write(ranked_df)

# Optional: Display a bar chart for better visualization of sentiment scores
fig = px.bar(ranked_df, x='Account', y='Overall Sentiment Score', color='Overall Sentiment Score',
             title="Overall Sentiment Score by Account", range_y=[0, 5])
st.plotly_chart(fig)


# Load data for the selected account
selected_file = account_files[account]
tweet_data = pd.read_csv(selected_file)



# Display dataset information
if st.checkbox("Show Raw Data"):
    st.write(tweet_data.head(50))

# Main analysis selection: Sentiment or Topic Analysis
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

    # Visualization options for sentiment distribution
    st.sidebar.subheader('Sentiment Visualization')
    sentiment_visualization = st.sidebar.selectbox("Select Visualization", ["Histogram", "Pie Chart"])

    # Count sentiments and display in chosen chart
    sentiment_counts = tweet_data['sentiment'].value_counts().reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']

    if sentiment_visualization == "Histogram":
        fig = px.bar(sentiment_counts, x='Sentiment', y='Count', color='Count', title=f'Sentiment Distribution for {account}')
        st.plotly_chart(fig)
    else:
        fig = px.pie(sentiment_counts, names='Sentiment', values='Count', title=f'Sentiment Distribution for {account}')
        st.plotly_chart(fig)

# Topic Analysis
elif analysis_type == "Topic Analysis":
    st.header("Topic Analysis")

    # Sidebar options for topic filtering
    st.sidebar.subheader('Filter by Topic')
    selected_topic = st.sidebar.selectbox("Select Topic", tweet_data['topics'].unique())
    topic_filtered_data = tweet_data[tweet_data['topics'] == selected_topic]

    st.write(f"### Tweets on the Topic: {selected_topic} for {account}")
    st.write(topic_filtered_data[['author_name', 'text', 'timestamp']].head(10))

    # Topic distribution visualization options
    st.sidebar.subheader("Topic Visualization")
    topic_visualization = st.sidebar.selectbox("Select Visualization Type", ["Bar Chart", "Pie Chart"])

    # Count topics and display in chosen chart
    topic_counts = tweet_data['topics'].value_counts().reset_index()
    topic_counts.columns = ['Topic', 'Count']

    if topic_visualization == "Bar Chart":
        fig = px.bar(topic_counts, x='Topic', y='Count', color='Count', title=f'Topic Frequency for {account}')
        st.plotly_chart(fig)
    else:
        fig = px.pie(topic_counts, names='Topic', values='Count', title=f'Topic Distribution for {account}')
        st.plotly_chart(fig)




st.header("Monthly Trends")

# Safely convert timestamp to datetime
try:
    # First check if timestamp is already datetime
    if not pd.api.types.is_datetime64_any_dtype(tweet_data['timestamp']):
        # If string, convert to datetime
        tweet_data['year_month'] = pd.to_datetime(tweet_data['timestamp'])
    else:
        tweet_data['year_month'] = tweet_data['timestamp']
        
    # Extract year-month
    tweet_data['year_month'] = tweet_data['year_month'].dt.to_period('M').dt.to_timestamp()
    
except Exception as e:
    st.error(f"Error converting timestamps: {str(e)}")
    st.write("Please ensure your timestamp column is in a recognized datetime format")
    st.stop()

# Monthly trends for sentiments
try:
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
    
    st.plotly_chart(fig_sentiment, use_container_width=True)
    
except Exception as e:
    st.error(f"Error creating sentiment trends: {str(e)}")

# Monthly trends for topics
try:
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
    
    st.plotly_chart(fig_topic, use_container_width=True)
    
except Exception as e:
    st.error(f"Error creating topic trends: {str(e)}")