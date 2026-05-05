'''
File to collect empirical data from
https://www.health.ny.gov/facilities/hospital/bed_capacity/
on patient arrivals and hospital bed capacity.
'''

import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time

start = time.time()

# dashboard for bed capacity across ny state hospitals 
dashboard_url = 'https://swww.health.ny.gov/facilities/hospital/bed_capacity/'

result = requests.get(dashboard_url)
if result.status_code != 200:
  print("something went wrong:", result.status_code, result.reason)

with open("bed_capacity.html", "w") as writer:
  writer.write(result.text)

with open("bed_capacity.html", "r") as reader:
  html_source = reader.read()

page = BeautifulSoup(html_source, "html.parser")

# find all park names mentioned on page
lis = page.find_all("li")
print("there are", len(lis), "list items on the page")

hospitals = []
for item in lis:
  park_name = re.findall(r'.+\s–', item.text)
  if len(park_name) != 0:
    hospitals.append(park_name[0][:-2])

hospitals = pd.Series(hospitals)
# first listed park in U.S.
i1 = parks[parks=="4D Farm"].index[0]
# last listed park in U.S.
i2 = parks[parks=="Villa Campestre"].index[0]
print(f'index of first listed park in U.S.: {i1}')
print(f'index of last listed park in U.S.: {i2}')
# filter list to only include parks in U.S.
parks = parks[i1:i2+1]
parks = parks.reset_index(drop=True)
print(parks.iloc[0])
print(parks.iloc[-1])
print(f'there are {len(parks)} listed parks in the U.S.')

parks.to_csv('parks.csv', header=False, index=False)