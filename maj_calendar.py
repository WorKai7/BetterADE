import requests

response = requests.get("https://edt.univ-littoral.fr/jsp/custom/modules/plannings/9n9Rr7WP.shu")


with open("planning.shu", "wb") as f:
    f.write(response.content)