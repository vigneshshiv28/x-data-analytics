import pandas as pd
from transformers import pipeline

# Load the dataset
file_path = "partially_processed_tweets/filtered_df_casheApp.csv"  
tweet_data = pd.read_csv(file_path)

# Initializing multilingual sentiment analysis pipeline
sentiment_pipeline = pipeline("text-classification", model="lxyuan/distilbert-base-multilingual-cased-sentiments-student")

# Function to classify sentiment using the pre-trained model
def get_sentiment(text):
    result = sentiment_pipeline(text)[0]
    return result['label'], result['score']

# Apply sentiment analysis to the text column
tweet_data['sentiment'] = tweet_data['text'].apply(lambda x: get_sentiment(x)[0] if isinstance(x, str) else "NEUTRAL")
tweet_data['sentiment_score'] = tweet_data['text'].apply(lambda x: get_sentiment(x)[1] if isinstance(x, str) else 0)

# Save the modified dataset to a new CSV
output_path = "final_tweets/CasheApp.csv"  
tweet_data.to_csv(output_path, index=False)

print(f"Sentiment analysis completed and saved to {output_path}")