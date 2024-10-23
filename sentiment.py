import streamlit as st
import pandas as pd
import plotly.express as px
from textblob import TextBlob

# Title of the app
st.title('Tweet Sentiment Analysis for Fibe India')

st.markdown('''This application allows you to analyze tweets related to Fibe India, 
including performing sentiment analysis to understand user sentiments.''')

# Sidebar description
st.sidebar.title("Fibe India Tweet Sentiment Analysis")
st.sidebar.markdown("This application performs sentiment analysis on tweets related to Fibe India.")

# Load the dataset
data = pd.read_csv('C:/Users/Khyati/Downloads/refined_data.csv')

# Function to classify sentiment using TextBlob
def get_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0:
        return 'positive'
    elif polarity == 0:
        return 'neutral'
    else:
        return 'negative'

# Apply sentiment analysis on the text column
data['sentiment'] = data['text'].apply(get_sentiment)

# Display the data
if st.checkbox("Show Data"):
    st.write(data.head(50))

# Sidebar for tweet filtering options
st.sidebar.subheader('Tweets Analyzer')
sentiment_choice = st.sidebar.radio('Sentiment Type', ('positive', 'negative', 'neutral'))

# Show a random tweet for the selected sentiment type
st.write(f"Random {sentiment_choice} tweet:")
st.write(data.query('sentiment==@sentiment_choice')[['text']].sample(1).iat[0, 0])

# Visualization Options
select = st.sidebar.selectbox('Visualization of Tweets', ['Histogram', 'Pie Chart'], key=1)

# Counting the number of tweets by sentiment
sentiment_count = data['sentiment'].value_counts()
sentiment_count_df = pd.DataFrame({'Sentiment': sentiment_count.index, 'Tweets': sentiment_count.values})

st.markdown("### Tweet count by sentiment")
if select == "Histogram":
    fig = px.bar(sentiment_count_df, x='Sentiment', y='Tweets', color='Tweets', height=500)
    st.plotly_chart(fig)
else:
    fig = px.pie(sentiment_count_df, values='Tweets', names='Sentiment')
    st.plotly_chart(fig)

# Tweet time analysis
st.sidebar.markdown('Time & Location of tweets')
hr = st.sidebar.slider("Hour of the day", 0, 23)
data['Date'] = pd.to_datetime(data['timestamp'])
hr_data = data[data['Date'].dt.hour == hr]

if not st.sidebar.checkbox("Hide", True, key='2'):
    st.markdown("### Location of the tweets based on the hour of the day")
    st.markdown(f"{len(hr_data)} tweets during {hr}:00 and {hr+1}:00")
    st.map(hr_data[['latitude', 'longitude']].dropna())

# Tweets by author filter
st.sidebar.markdown("Tweets by author")
author_filter = st.sidebar.multiselect("Select Authors", data['author_name'].dropna().unique(), key='0')

if len(author_filter) > 0:
    filtered_data = data[data['author_name'].isin(author_filter)]
    fig1 = px.histogram(filtered_data, x='author_name', y='sentiment', histfunc='count', color='sentiment')
    st.plotly_chart(fig1)
