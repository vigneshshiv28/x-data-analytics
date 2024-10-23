from transformers import pipeline

# Load the pipeline with the text classification model
pipe = pipeline("text-classification", model="lxyuan/distilbert-base-multilingual-cased-sentiments-student")

# Classify a piece of text
result = pipe("Ye koi solution nahi huaa team Maine apse request Kara hai 5-6 month meri emi ko hold kare taki uske baad me continue emi pay karke apka dues clear kar saku. But agar apke recovery agents ne harrass hi karna hai to fine majboori  mere next step ke liye you will be responsible")

# Print the result
print(result)
