import json

with open("repos.json") as f:
    repos = json.load(f)

print('{"include" : [')
items = list(repos.items())


def _println(repo, url):
    slug = repo.replace("-", "_")
    print(
        f'  {{ "module_name": "{repo}", "url": "{url}", "keyname": "{slug}"}} ', end=""
    )


for repo, url in items[:-1]:
    _println(repo, url)
    print(",", end="")
_println(items[-1][0], items[-1][1])
print("]}")
