# Write your code here :-)

import os
import json

import secrets

print("Hello World!")

print(secrets.creds_dict)

## settings.toml
print(os.getenv("test_variable"))

## JSON
secrets_dict = {
    'key1': 'asdf',
    'key2': 'qwer',
    'key3': 'foobar',
}
## Speichern in einer JSON-Datei
# with open('secrets.json', 'w') as f:
#     json.dump(secrets_dict, f, indent=4)  # indent sorgt für bessere Lesbarkeit
## Laden der JSON-Datei
with open('secrets.json', 'r') as f:
    secrets_dict = json.load(f)
print(secrets_dict)

print(secrets.creds_dict)
