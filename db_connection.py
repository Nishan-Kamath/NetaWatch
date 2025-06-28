from pymongo import MongoClient

# Your credentials
username = "nishankamath"
password = "@K1a2m3a4t5h6"  # Needs URL encoding due to special characters like '@'

# URL-encode the password properly
from urllib.parse import quote_plus
encoded_password = quote_plus(password)

# Construct connection URI
uri = "mongodb+srv://nishankamath:nishankamath@cluster0.emhkoj2.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Connect to MongoDB
client = MongoClient(uri)

# Access your specific database
db = client["NetaWatch"]
users_col = db["users"]

#users_col.insert_one({'email':'nishankamath@gmail.com','full_name':'Nishan Kamath'})

for user in users_col.find():
    print(user)