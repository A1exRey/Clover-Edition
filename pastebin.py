from urllib import request, error
import re
import os
from utils import *
from pathlib import Path

fnamesSoFar = {}


def filename(s):
    fname = re.sub("-$", "", re.sub("^-", "", re.sub("[^а-яА-Яa-zA-Z0-9_-]+", "-", s)))
    n = 1
    fname2 = fname
    while fname2 in fnamesSoFar:
        n += 1
        fname2 = fname + "-" + str(n)
    fnamesSoFar[fname2] = True
    return fname2


try:
    with open('./data/promts.txt','r') as fp: paste = fp.read()
    #paste = request.urlopen("https://pastebin.com/raw/KD4yN2Gc").read().decode("utf-8")
except error.HTTPError as e:
    if e.code == 404:
        output("Unable to find pastebin for scraping.", "error")
    else:
        output("Unable to load pastebin for custom prompts. Error code: {}".format(e.code), "error")
except error.URLError as e:
    output("Unexpected error while trying to load pastebin prompts! Error code: {}".format(e.code), "error")
paste = re.sub(r'\nTAGS:.*\n', '\n', paste)
#pipe is never used in paste so use it as a seperator
paste = re.sub("=====+", "|", paste)
paste = re.sub("\r", "", paste)
paste = re.sub("\n\s*\n\s*", "\n\n", paste)
sections = re.findall(r"[^|]+", paste)
for sect in sections[2:][:-1]:
    category = re.search(r"\*\*\*([^\*]+)\*\*\*", sect).group(1)
    category = re.sub(".[сС]южеты?$", "", category)
    category = filename(category)
    try:  
        Path("prompts", category).mkdir(exist_ok=True)
        print(category)
    except IOError:
        output("Permission error! Unable to create directory for custom prompts.", "error")
    for story in [x for x in filter(None, sect.split("\n\n"))][1:]:
        title = re.search(r"^\(([^\)]+)", story)
        if bool(title):
            title = title.group(1)
        else:
            title = story[:30]
        title = filename(title) + ".txt"
        with Path("prompts", category, title).open("w", encoding="UTF-8") as f:
            try:
                f.write(re.sub(r"^\([^\)]+\)\n", "", story))
            except IOError:
                output("Permission error! Unable to write custom prompt to file.", "error")
