#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys,re,time
import csv
import urllib
import urllib2
import feedparser
import json
import argparse
import chardet
from pyquery import PyQuery as pq
import itertools
import traceback

reload(sys)
sys.setdefaultencoding('utf-8')


# get hatena entrylist with HTML
def get_hatena_entrylist(of, bookmark_threshold):
    urls = []
    try:
        # get the webpage
        base_url = 'http://b.hatena.ne.jp/entrylist?of=%s&threshold=%s' \
                % (of, bookmark_threshold)
        data = ''.join(urllib.urlopen(base_url).readlines())

        # set character
        guess = chardet.detect(data)
        result = dict(url=base_url,data=data,**guess)
        unicoded = result['data'].decode(result['encoding'])

        # scrape the webpage
        d = pq(unicoded)
        for link in d.find('a[class="entry-link"]'):
            url = pq(link).attr.href
            title = pq(link).attr.title
            timestamp = pq(link).parent().parent().\
                    children('ul li[class="date"]').text()
            urls.append([url, title, timestamp])
    except:
        pass

    return urls


# get hatena entrylist with RSS
def get_hatena_search(of, search_target, query):
    urls = []
    try:
        # get the webpage
        base_url = 'http://b.hatena.ne.jp/search/%s?mode=rss&of=%s&q=%s' \
                % (search_target, of, urllib2.quote(query.encode("utf-8")))
        opener = urllib2.build_opener()
        response = opener.open(base_url)
        content = response.read()
        feed = feedparser.parse(content)
        if feed["entries"] == []:
            raise

        # scrape the rss
        for e in feed["entries"]:
            try:
                url = e['link']
                title = re.sub("[,\"]", '', e['title'])
                timestamp = time.strftime('%Y/%m/%d %H:%M', e['updated_parsed'])
                urls.append([url, title, timestamp])
            except:
                print(traceback.format_exc())
                pass
    except:
        pass

    return urls


# create CSV of url list
def create_url_list(feed_max, bookmark_threshold, dest_urls, feed_target, query):
    # write url list with CSV.
    fout = open(dest_urls, 'w')
    writer = csv.writer(fout, delimiter=",")
    writer.writerow(["id", "url", "title", "timestamp"])

    # get the target urls.
    print("get target urls.")
    feed_interval = 20
    if feed_target == 'tag':
        feed_interval = 40
    url_id = 0
    for i in range(0, feed_max, feed_interval):
        # get urls.
        urls = []
        if feed_target == 'tag':
            urls = get_hatena_search(i, feed_target, query)
        elif feed_target == 'entrylist':
            urls = get_hatena_entrylist(i, bookmark_threshold)
        else:
            raise

        # write csv.
        for id, url in enumerate(urls):
            print('%d: %s' % (url_id, url[1]))
            writer.writerow([url_id] + url)
            url_id += 1

        time.sleep(0.05)
    fout.close()


# create CSV of tag cooccurrence
def create_cooccurrence(\
        dest_urls,\
        dest_cooccurrence,\
        cooccurence_threshold):
    # read url list from CSV.
    fin = open(dest_urls, 'r')
    reader = csv.reader(fin)
    header = next(reader)

    # get bookmarks each urls.
    tag_cotag_freq = {} # {tag: {cotag: freq}}
    opener = urllib2.build_opener()
    print("\nextract each urls:")
    for row in reader:
        try:
            [url_id, url, title, timestamp] = row
            print("%s: %s" % (url_id, title))
            response = opener.open("http://b.hatena.ne.jp/entry/jsonlite/" + url)
            content = response.read()
            tmp = json.loads(content)
            if (tmp == None) or ('bookmarks' not in tmp):
                print('skipped %s.' % (url))
                continue

            # get all tags added the webpage
            tags = []
            for b in tmp["bookmarks"]:
                for tag in b['tags']:
                    normalized_tag = re.sub("[ -]", "", tag).lower()
                    if normalized_tag not in tags:
                        tags.append(normalized_tag)
            tags.sort()

            # calculate cooccurrance
            for tag, cotag in list(itertools.combinations(tags, 2)):
                if tag not in tag_cotag_freq:
                    tag_cotag_freq[tag] = {cotag: 1}
                else:
                    if cotag not in tag_cotag_freq[tag]:
                        tag_cotag_freq[tag][cotag] = 1
                    else:
                        tag_cotag_freq[tag][cotag] += 1
            time.sleep(0.05)
        except:
            print traceback.format_exc()
            print('error occured.')
            pass
    fin.close()

    # write inverted url list with CSV.
    fout = open(dest_cooccurrence, 'w')
    writer = csv.writer(fout, delimiter=",")
    writer.writerow(["tag", "co_tag", "freq"])
    for tag, cotag_freq in tag_cotag_freq.items():
        for cotag, freq in cotag_freq.items():
            if freq >= cooccurence_threshold:
                writer.writerow([tag, cotag, freq])
    fout.close()


if __name__ == "__main__":
    # parse args
    parser = argparse.ArgumentParser(\
            description='This script create the CSV describing cooccurrence of tags at Hatena bookmark.')
    parser.add_argument(\
            '-d', '--dest-url-list', \
            action='store', \
            nargs='?', \
            const=None, \
            default='./url_list.csv', \
            type=str, \
            choices=None, \
            help='directory path where you want to create output CSV for URL list (default: "./url_list.csv")', \
            metavar=None)
    parser.add_argument(\
            '-D', '--dest-cooccurrence', \
            action='store', \
            nargs='?', \
            const=None, \
            default='./cooccurrence.csv', \
            type=str, \
            choices=None, \
            help='directory path where you want to create output CSV for cooccurrence list of tags (default: "./cooccurrence.csv")', \
            metavar=None)
    parser.add_argument(\
            '-s', '--feed-target', \
            action='store', \
            nargs='?', \
            const=None, \
            default='entrylist', \
            type=str, \
            choices=['entrylist', 'tag'], \
            help='feed target for feeding webpages. "entrylist" means getting all entries, and "tag" means getting only entries of tagged query by "--feed-query" (default: "entrylist")', \
            metavar=None)
    parser.add_argument(\
            '-q', '--feed-query', \
            action='store', \
            nargs='?', \
            const=None, \
            default='', \
            type=str, \
            choices=None, \
            help='query for feeding webpages. this parameter make sense only at "--feed-target" is "tag" (default: "")', \
            metavar=None)
    parser.add_argument(\
            '-f', '--feed-max', \
            action='store', \
            nargs='?', \
            const=None, \
            default=10000, \
            type=int, \
            choices=None, \
            help='max page for feeding web pages (default: 10000)', \
            metavar=None)
    parser.add_argument(\
            '-b', '--bookmark-threshold', \
            action='store', \
            nargs='?', \
            const=None, \
            default=10, \
            type=int, \
            choices=None, \
            help='minimum bookmarks for feeding web pages (default: 100)', \
            metavar=None)
    parser.add_argument(\
            '-c', '--cooccurence-threshold', \
            action='store', \
            nargs='?', \
            const=None, \
            default=10, \
            type=int, \
            choices=None, \
            help='minimum cooccurence of tags (default: 10)', \
            metavar=None)
    args = parser.parse_args()

    # get target urls then write to CSV.
    create_url_list(\
            args.feed_max,\
            args.bookmark_threshold,\
            args.dest_url_list,\
            args.feed_target,\
            args.feed_query)

    # get bookmarks each urls then write to CSV.
    create_cooccurrence(\
            args.dest_url_list,\
            args.dest_cooccurrence,\
            args.cooccurence_threshold)

    # inform successfully process completed.
    print((\
            '\nprocess is successfully completed. check following files.' +\
            '\n    URL list:          %s' +\
            '\n    cooccurrence tags: %s'\
          ) % (args.dest_url_list, args.dest_cooccurrence))
