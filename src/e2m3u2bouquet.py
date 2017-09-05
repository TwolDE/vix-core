"""
e2m3u2bouquet.e2m3u2bouquet -- Enigma2 IPTV m3u to bouquet parser

@author:     Dave Sully, Doug Mackay
@copyright:  2017 All rights reserved.
@license:    GNU GENERAL PUBLIC LICENSE version 3
@deffield    updated: Updated
"""

import sys
import os
import re
import unicodedata
import datetime
import urllib
import imghdr
import tempfile
import glob
import ssl
import hashlib
import base64
from PIL import Image
from collections import OrderedDict
from collections import deque
from xml.etree import ElementTree
from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter

__all__ = []
__version__ = '0.6.1'
__date__ = '2017-06-04'
__updated__ = '2017-08-26'

DEBUG = 0
TESTRUN = 0

ENIGMAPATH = '/etc/enigma2/'
EPGIMPORTPATH = '/etc/epgimport/'
CFGPATH = os.path.join(ENIGMAPATH, 'e2m3u2bouquet/')
PICONSPATH = '/usr/share/enigma2/picon/'
PROVIDERS = {}
PROVIDERSURL = 'https://raw.githubusercontent.com/su1s/e2m3u2bouquet/master/providers.enc'

class CLIError(Exception):
    """Generic exception to raise and log different fatal errors."""
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = 'E: %s' % msg

    def __str__(self):
        return self.msg

    def __unicode__(self):
        return self.msg


class IPTVSetup():

    def __init__(self):
        print '\n********************************'
        print 'Starting Engima2 IPTV bouquets'
        print str(datetime.datetime.now())
        print '********************************\n'

    def uninstaller(self):
        """Clean up routine to remove any previously made changes"""
        print '[e2m3u2bouquet]----Running uninstall----'
        try:
            print '[e2m3u2bouquet]Removing old IPTV bouquets...'
            for fname in os.listdir(ENIGMAPATH):
                if 'userbouquet.suls_iptv_' in fname:
                    os.remove(os.path.join(ENIGMAPATH, fname))
                elif 'bouquets.tv.bak' in fname:
                    os.remove(os.path.join(ENIGMAPATH, fname))

            print '[e2m3u2bouquet]Removing IPTV custom channels...'
            if os.path.isdir(EPGIMPORTPATH):
                for fname in os.listdir(EPGIMPORTPATH):
                    if 'suls_iptv_' in fname:
                        os.remove(os.path.join(EPGIMPORTPATH, fname))

            print '[e2m3u2bouquet]Removing IPTV bouquets from bouquets.tv...'
            os.rename(os.path.join(ENIGMAPATH, 'bouquets.tv'), os.path.join(ENIGMAPATH, 'bouquets.tv.bak'))
            tvfile = open(os.path.join(ENIGMAPATH, 'bouquets.tv'), 'w+')
            bakfile = open(os.path.join(ENIGMAPATH, 'bouquets.tv.bak'))
            for line in bakfile:
                if '.suls_iptv_' not in line:
                    tvfile.write(line)
            bakfile.close()
            tvfile.close()
        except Exception as e:
            raise e
        print '[e2m3u2bouquet]----Uninstall complete----'

    def download_m3u(self, url):
        """Download m3u file from url"""
        path = tempfile.gettempdir()
        filename = os.path.join(path, 'e2m3u2bouquet.m3u')
        print '\n[e2m3u2bouquet]----Downloading m3u file----'
        if DEBUG:
            print 'm3uurl = {}'.format(url)
        try:
            urllib.urlretrieve(url, filename)
        except Exception as e:
            raise e
        return filename

    def download_providers(self, url):
        """Download providers file from url"""
        # create e2m3u2bouquet config folder if it doesn't exist
        if not os.path.isdir(CFGPATH):
            os.makedirs(CFGPATH)
        filename = os.path.join(CFGPATH, 'IPTVcreate_providers.txt')
        print("[e2m3u2bouquet]----Downloading providers file----")
        if DEBUG:
            print '[e2m3u2bouquet]providers url = {}'.format(url)
        try:
            # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context = ssl._create_unverified_context()
            urllib.urlretrieve(url, filename, context=context)
            return filename
        except Exception:
            pass    # fallback to no ssl context
        try:
            urllib.urlretrieve(url, filename)
            return filename
        except Exception, e:
           raise e

    def download_bouquet(self, url):
        """Download panel bouquet file from url"""
        path = tempfile.gettempdir()
        filename = os.path.join(path, 'userbouquet.panel.tv')
        print '\n[e2m3u2bouquet]----Downloading providers bouquet file----'
        if DEBUG:
            print 'bouqueturl = {}'.format(url)
        try:
            urllib.urlretrieve(url, filename)
        except Exception as e:
            raise e
        return filename

    def parse_panel_bouquet(self, panel_bouquet_file):
        """Check providers bouquet for custom service references
        """
        panel_bouquet = {}

        if os.path.isfile(panel_bouquet_file):
            with open(panel_bouquet_file, 'r') as f:
                for line in f:
                    if '#SERVICE' in line:
                        # get service ref values we need (dict value) and stream file (dict key)
                        service = line.strip().split(':')
                        if len(service) == 11:
                            pos = service[10].rfind('/')
                            if pos != -1 and pos + 1 != len(service[10]):
                                key = service[10][pos + 1:]
                                value = ':'.join((service[3], service[4], service[5], service[6]))
                                if value != '0:0:0:0':
                                    # only add to dict if a custom service id is present
                                    panel_bouquet[key] = value
            if not DEBUG:
                # remove panel bouquet file
                os.remove(panel_bouquet_file)
        return panel_bouquet

    def parse_m3u(self, filename, all_iptv_stream_types, panel_bouquet, xcludesref):
        """core parsing routine"""
        # Extract and generate the following items from the m3u
        # group-title
        # tvg-name
        # tvg-id
        # tvg-logo
        # stream-name
        # stream-url
        print '\n[e2m3u2bouquet]----Parsing m3u file----'
        try:
            if not os.path.getsize(filename):
                raise Exception('M3U file is empty. Check username & password')
        except Exception as e:
            raise e

        self.uninstaller()
        category_order = []
        category_options = {}
        dictchannels = OrderedDict()
        with open(filename, 'r') as f:
            for line in f:
                if 'EXTM3U' in line:  # First line we are not interested
                    continue
                elif 'EXTINF:' in line:  # Info line - work out group and output the line
                    channeldict = {'tvg-id': '','tvg-name': '','tvg-logo': '','group-title': '','stream-name': '','stream-url': '','enabled': True,
                       'nameOverride': '',
                       'serviceRef': '',
                       'serviceRefOverride': False
                       }
                    channel = line.split('"')
                    # strip unwanted info at start of line
                    pos = channel[0].find(' ')
                    channel[0] = channel[0][pos:]

                    # loop through params and build dict
                    for i in xrange(0, len(channel) - 2, 2):
                        channeldict[channel[i].lower().strip(' =')] = channel[i + 1].decode('utf-8')

                    # Get the stream name from end of line (after comma)
                    stream_name_pos = line.rfind(',')
                    if stream_name_pos != -1:
                        channeldict['stream-name'] = line[stream_name_pos + 1:].strip().decode('utf-8')

                    # Set default name for any blank groups
                    if channeldict['group-title'] == '':
                        channeldict['group-title'] = u'None'

                    if not (channeldict['tvg-id'] or channeldict['group-title']):
                        raise Exception("No extended playlist info found. Check m3u url should be 'type=m3u_plus'")
                elif 'http:' in line:
                    channeldict['stream-url'] = line.strip()

                    self.set_streamtypes_vodcats(channeldict, all_iptv_stream_types)

                    if channeldict['group-title'] not in dictchannels:
                        dictchannels[channeldict['group-title']] = [channeldict]
                    else:
                        dictchannels[channeldict['group-title']].append(channeldict)

        category_order = dictchannels.keys()

        # sort categories by custom order (if exists)
        sorted_categories, category_options = self.parse_map_bouquet_xml(dictchannels)
        sorted_categories.extend(category_order)
        # remove duplicates, keep order
        category_order = OrderedDict((x, True) for x in sorted_categories).keys()

        # Check for and parse override map
        self.parse_map_channels_xml(dictchannels, xcludesref)

        # Add Service references
        # VOD won't have epg so use same service id for all VOD
        vod_service_id = 65535
        serviceid_start = 34000
        category_offset = 150
        catstartnum = serviceid_start

        for cat in category_order:
            num = catstartnum
            if cat in dictchannels:
                if not cat.startswith('VOD'):
                    if cat in category_options:
                        # check if we have cat idStart from override file
                        if category_options[cat]['idStart'] > 0:
                            num = category_options[cat]['idStart']
                        else:
                            category_options[cat]['idStart'] = num
                    else:
                        category_options[cat] = {'idStart': num}

                    for x in dictchannels[cat]:
                        cat_id = self.get_category_id(cat)
                        service_ref = '{:x}:{}:{}:0'.format(num, cat_id[:4], cat_id[4:])
                        if panel_bouquet:
                            # check if we have the panels custom service ref
                            pos = x['stream-url'].rfind('/')
                            if pos != -1 and pos + 1 != len(x['stream-url']):
                                m3u_stream_file = x['stream-url'][pos + 1:]
                                if m3u_stream_file in panel_bouquet:
                                    # have a match use the panels custom service ref
                                    service_ref = panel_bouquet[m3u_stream_file]
                        if not x['serviceRefOverride']:
                            # if service ref is not overridden in xml update
                            x['serviceRef'] = '{}:0:1:{}:0:0:0'.format(x['stream-type'], service_ref)
                        num += 1
                else:
                    for x in dictchannels[cat]:
                        x['serviceRef'] = '{}:0:1:{:x}:0:0:0:0:0:0'.format(x['stream-type'], vod_service_id)
            while catstartnum < num:
                catstartnum += category_offset

        # move all VOD categories to VOD placeholder position
        if 'VOD' in category_order:
            vodindex = category_order.index('VOD')
            vodcategories = list((cat for cat in category_order if cat.startswith('VOD -')))
            if len(vodcategories):
                # remove the multi vod categories from their current location
                category_order = [ x for x in category_order if x not in vodcategories ]
                # insert the multi vod categories at the placeholder pos
                category_order[vodindex:vodindex] = vodcategories
                category_order.remove('VOD')

        # Have a look at what we have
        if DEBUG and TESTRUN:
            datafile = open(os.path.join(CFGPATH, 'channels.debug'), "w+")
            for cat in category_order:
                if cat in dictchannels:
                    for line in dictchannels[cat]:
                        linevals = ''
                        for key, value in line.items():
                            if type(value) is bool:
                                linevals += str(value) + ':'
                            else:
                                linevals += value.encode('utf-8') + ':'
                        datafile.write('{}\n'.format(linevals))
            datafile.close()
        print '[e2m3u2bouquet]Completed parsing data...'

        if not DEBUG:
            # remove m3u file
            if os.path.isfile(filename):
                os.remove(filename)
        return (category_order, category_options, dictchannels)

    def set_streamtypes_vodcats(self, channeldict, all_iptv_stream_types):
        """Set the stream types and VOD categories
        """
        if (channeldict['stream-url'].endswith('.ts') or channeldict['stream-url'].endswith('.m3u8')) and not channeldict['group-title'].startswith('VOD'):
            channeldict['stream-type'] = '4097' if all_iptv_stream_types else '1'
        else:
            channeldict['group-title'] = u'VOD - {}'.format(channeldict['group-title'])
            channeldict['stream-type'] = '4097'

    def parse_map_bouquet_xml(self, dictchannels):
        """Check for a mapping override file and parses it if found
        """
        category_order = []
        category_options = {}
        mapping_file = self.get_mapping_file()
        if mapping_file:
            print '\n[e2m3u2bouquet]----Parsing custom bouquet order----'

            with open(mapping_file, 'r') as f:
                tree = ElementTree.parse(f)
            for node in tree.findall('.//category'):
                dictoption = {}

                category = node.attrib.get('name')
                if not type(category) is unicode:
                    category = category.decode("utf-8")
                cat_title_override = node.attrib.get('nameOverride', '')
                if not type(cat_title_override) is unicode:
                    cat_title_override = cat_title_override.decode("utf-8")
                dictoption['nameOverride'] = cat_title_override
                dictoption['idStart'] = int(node.attrib.get('idStart', '0')) \
                    if node.attrib.get('idStart', '0').isdigit() else 0
                if node.attrib.get('enabled') == 'false':
                    dictoption["enabled"] = False
                    # Remove category/bouquet
                    if category != "VOD":
                        if category in dictchannels:
                            dictchannels.pop(category, None)
                    else:
                        keys_to_remove = []
                        for k in dictchannels.iterkeys():
                            if k.startswith("VOD"):
                                keys_to_remove.append(k)
                        if keys_to_remove:
                            for k in keys_to_remove:
                                dictchannels.pop(k, None)
                else:
                    dictoption["enabled"] = True
                    category_order.append(category)

                category_options[category] = dictoption

            print '[e2m3u2bouquet]custom bouquet order parsed...'
        return category_order, category_options

    def parse_map_xmltvsources_xml(self):
        """Check for a mapping override file and parses it if found
        """
        list_xmltv_sources = {}
        mapping_file = self.get_mapping_file()
        if mapping_file:
            with open(mapping_file, 'r') as f:
                tree = ElementTree.parse(f)
                for group in tree.findall('.//xmltvextrasources/group'):
                    group_name = group.attrib.get('id')
                    urllist = []
                    for url in group:
                        urllist.append(url.text)
                    list_xmltv_sources[group_name] = urllist
        return list_xmltv_sources

    def parse_map_channels_xml(self, dictchannels, xcludesref):
        """Check for a mapping override file and applies it if found
        """
        mappingfile = self.get_mapping_file()
        if mappingfile:
            print '\n----Parsing custom channel order, please be patient----'
            with open(mappingfile, 'r') as f:
                tree = ElementTree.parse(f)
            for cat in dictchannels:
                if not cat.startswith('VOD'):
                    # We don't override any individual VOD streams
                    print '[e2m3u2bouquet]sorting {}'.format(cat.encode('utf-8'))
                    sortedchannels = []
                    listchannels = []
                    for x in dictchannels[cat]:
                        listchannels.append(x['stream-name'])
                    for node in tree.findall(u'.//channel[@category="{}"]'.format(cat)):
                        sortedchannels.append(node.attrib.get('name'))

                    sortedchannels.extend(listchannels)
                    # remove duplicates, keep order
                    listchannels = OrderedDict((x, True) for x in sortedchannels).keys()

                    # sort the channels by new order
                    channel_order_dict = {channel: index for index, channel in enumerate(listchannels)}
                    dictchannels[cat].sort(key=lambda x: channel_order_dict[x['stream-name']])

                    for x in dictchannels[cat]:
                        node = tree.find(u'.//channel[@name="{}"]'.format(x['stream-name']))
                        if node is not None:
                            if node.attrib.get('enabled') == 'false':
                                x['enabled'] = False
                            x['nameOverride'] = node.attrib.get('nameOverride', '')
                            # default to current values if attribute doesn't exist
                            x['tvg-id'] = node.attrib.get('tvg-id', x['tvg-id'])
                            if node.attrib.get('serviceRef', None) and not xcludesref:
                                x['serviceRef'] = node.attrib.get('serviceRef', x['serviceRef'])
                                x['serviceRefOverride'] = True
                            # streamUrl no longer output to xml file but we still check and process it
                            x['stream-url'] = node.attrib.get('streamUrl', x['stream-url'])
                            clear_stream_url = node.attrib.get('clearStreamUrl') == 'true'
                            if clear_stream_url:
                                x['stream-url'] = ''

            print '[e2m3u2bouquet]custom channel order parsed...'

    def save_map_xml(self, categoryorder, category_options, dictchannels, list_xmltv_sources):
        """Create mapping file"""
        mappingfile = os.path.join(CFGPATH, 'e2m3u2bouquet-sort-current.xml')
        indent = '  '
        vod_category_output = False

        if dictchannels:
            with open(mappingfile, "wb") as f:
                f.write('<!--\r\n')
                f.write('{} e2m3u2bouquet Custom mapping file\r\n'.format(indent))
                f.write('{} Rearrange bouquets or channels in the order you wish\r\n'.format(indent))
                f.write('{} Disable bouquets or channels by setting enabled to "false"\r\n'.format(indent))
                f.write('{} Map DVB EPG to IPTV by changing channel serviceRef attribute to match DVB service reference\r\n'.format(indent))
                f.write('{} Map XML EPG to different feed by changing channel tvg-id attribute\r\n'.format(indent))
                f.write('{} Rename this file as e2m3u2bouquet-sort-override.xml for changes to apply\r\n'.format(indent))
                f.write('-->\r\n')

                f.write('<mapping>\r\n')

                f.write('{}<xmltvextrasources>\r\n'.format(indent))
                if not list_xmltv_sources:
                    # output example config
                    f.write('{}<!-- Example Config\r\n'.format((2 * indent)))
                    # uk
                    f.write('{}<group id="{}">\r\n'.format(2 * indent, 'uk'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://www.xmltvepg.nl/rytecxmltv-UK.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://rytecepg.ipservers.eu/epg_data/rytecxmltv-UK.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://rytecepg.wanwizard.eu/rytecxmltv-UK.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://91.121.106.172/~rytecepg/epg_data/rytecxmltv-UK.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://www.vuplus-community.net/rytec/rytecxmltv-UK.gz'))
                    f.write('{}</group>\r\n'.format(2 * indent))
                    # de
                    f.write('{}<group id="{}">\r\n'.format(2 * indent, 'de'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://www.xmltvepg.nl/rytecxmltvGermany.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://rytecepg.ipservers.eu/epg_data/rytecxmltvGermany.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://rytecepg.wanwizard.eu/rytecxmltvGermany.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://91.121.106.172/~rytecepg/epg_data/rytecxmltvGermany.gz'))
                    f.write('{}<url>{}</url>\r\n'.format(3 * indent, 'http://www.vuplus-community.net/rytec/rytecxmltvGermany.gz'))
                    f.write('{}</group>\r\n'.format(2 * indent))
                    f.write('{}-->\r\n'.format(2 * indent))
                else:
                    for group in list_xmltv_sources:
                        f.write('{}<group id="{}">\r\n'.format(2 * indent, self.xml_escape(group)))
                        for source in list_xmltv_sources[group]:
                            f.write('{}<url>{}</url>\r\n'.format(3 * indent, self.xml_escape(source)))
                        f.write('{}</group>\r\n'.format(2 * indent))
                f.write('{}</xmltvextrasources>\r\n'.format(indent))

                f.write('{}<categories>\r\n'.format(indent))
                for cat in categoryorder:
                    if cat in dictchannels:
                        if not cat.startswith('VOD -'):
                            cat_title_override = ''
                            idStart = ''
                            if cat in category_options:
                                cat_title_override = category_options[cat].get('nameOverride', '')
                                idStart = category_options[cat].get('idStart', '')
                            f.write('{}<category name="{}" nameOverride="{}" idStart="{}" enabled="true" />\r\n'
                                    .format(2 * indent,
                                            self.xml_escape(cat).encode('utf-8'),
                                            self.xml_escape(cat_title_override).encode('utf-8'),
                                            idStart
                                            ))
                        elif not vod_category_output:
                            # Replace multivod categories with single VOD placeholder
                            cat_title_override = ''
                            if 'VOD' in category_options:
                                cat_title_override = category_options['VOD'].get('nameOverride', '')
                            f.write('{}<category name="{}" nameOverride="{}" enabled="true" />\r\n'
                                    .format(2 * indent,
                                            'VOD',
                                            self.xml_escape(cat_title_override).encode('utf-8'),
                                            ))
                            vod_category_output = True
                for cat in category_options:
                    if 'enabled' in category_options[cat] and category_options[cat]['enabled'] is False:
                        f.write('{}<category name="{}" nameOverride="{}" enabled="false" />\r\n'
                                .format(2 * indent,
                                        self.xml_escape(cat).encode("utf-8"),
                                        self.xml_escape(cat_title_override).encode("utf-8")
                                        ))

                f.write('{}</categories>\r\n'.format(indent))

                f.write('{}<channels>\r\n'.format(indent))
                for cat in categoryorder:
                    if cat in dictchannels:
                        # Don't output any of the VOD channels
                        if not cat.startswith('VOD'):
                            f.write('{}<!-- {} -->\r\n'.format(2 * indent, self.xml_escape(cat.encode('utf-8'))))
                            for x in dictchannels[cat]:
                                f.write('{}<channel name="{}" nameOverride="{}" tvg-id="{}" enabled="{}" category="{}" serviceRef="{}" clearStreamUrl="{}" />\r\n'
                                        .format(2 * indent,
                                                self.xml_escape(x['stream-name'].encode('utf-8')),
                                                self.xml_escape(x.get('nameOverride', '').encode('utf-8')),
                                                self.xml_escape(x['tvg-id'].encode('utf-8')),
                                                str(x['enabled']).lower(),
                                                self.xml_escape(cat.encode('utf-8')),
                                                self.xml_escape(x['serviceRef']),
                                                'false' if x['stream-url'] else 'true'
                                                ))

                f.write('{}</channels>\r\n'.format(indent))
                f.write('</mapping>')

    def download_picons(self, dictchannels, iconpath):
        print '\n[e2m3u2bouquet]----Downloading Picon files, please be patient----'
        print '[e2m3u2bouquet]If no Picons exist this will take a few minutes'
        if not os.path.isdir(iconpath):
            os.makedirs(iconpath)

        for cat in dictchannels:
            if not cat.startswith('VOD'):
                # Download Picon if not VOD
                for x in dictchannels[cat]:
                    self.download_picon_file(x['tvg-logo'], self.get_service_title(x), iconpath)

        print '\n[e2m3u2bouquet]Picons download completed...'
        print '[e2m3u2bouquet]Box will need restarted for Picons to show...'

    def download_picon_file(self, logourl, title, iconpath):
        if logourl:
            if not logourl.startswith('http'):
                logourl = 'http://{}'.format(logourl)
            piconname = self.get_picon_name(title)
            piconfilepath = os.path.join(iconpath, piconname)
            existingpicon = filter(os.path.isfile, glob.glob(piconfilepath + '*'))

            if not existingpicon:
                if DEBUG:
                    print "[e2m3u2bouquet]Picon file doesn't exist downloading"
                    print '[e2m3u2bouquet]PiconURL: {}'.format(logourl)
                else:
                    # Output some kind of progress indicator
                    sys.stdout.write('.')
                    sys.stdout.flush()
                try:
                    urllib.urlretrieve(logourl, piconfilepath)
                except Exception as e:
                    if DEBUG:
                        print e
                    return
                self.picon_post_processing(piconfilepath)

    def picon_post_processing(self, piconfilepath):
        """Check type of image received and convert to png
        if necessary
        """
        ext = ''
        # get image type
        try:
            ext = imghdr.what(piconfilepath)
        except Exception as e:
            if DEBUG:
                print e
            return
        # if image but not png convert to png
        if ext is not None and ext is not 'png':
            if DEBUG:
                print '[e2m3u2bouquet] Converting Picon to png'
            try:
                Image.open(piconfilepath).save('{}.{}'.format(piconfilepath, 'png'))
            except Exception as e:
                if DEBUG:
                    print e
                return
            try:
                # remove non png file
                os.remove(piconfilepath)
            except Exception as e:
                if DEBUG:
                    print e
                return
        else:
            # rename to correct extension
            try:
                os.rename(piconfilepath, '{}.{}'.format(piconfilepath, ext))
            except Exception as e:
                if DEBUG:
                    print e
            pass

    def get_picon_name(self, serviceName):
        """Convert the service name to a Picon Service Name
        """
        name = serviceName
        if type(name) is unicode:
            name = name.encode('utf-8')
        name = unicodedata.normalize('NFKD', unicode(name, 'utf_8')).encode('ASCII', 'ignore')
        exclude_chars = ['/', '\\', "'", '"', '`', '?', ' ', '(', ')', ':', '<', '>', '|', '.', '\n', '!']
        name = re.sub('[%s]' % ''.join(exclude_chars), '', name)
        name = name.replace('&', 'and')
        name = name.replace('+', 'plus')
        name = name.replace('*', 'star')
        name = name.lower()
        return name

    def get_safe_filename(self, filename):
        """Convert filename to safe filename
        """
        name = filename.replace(' ', '_').replace('/', '_')
        if type(name) is unicode:
            name = name.encode('utf-8')
        name = unicodedata.normalize('NFKD', unicode(name, 'utf_8')).encode('ASCII', 'ignore')
        exclude_chars = ['/', '\\', "'", '"', '`',
         '?', ' ', '(', ')', ':', '<', '>',
         '|', '.', '\n', '!', '&', '+', '*']
        name = re.sub('[%s]' % ''.join(exclude_chars), '', name)
        name = name.lower()
        return name

    def get_current_bouquet_indexes(self):
        """Get the bouquet indexes (ex iptv)
        """
        current_bouquets_indexes =[]

        with open(os.path.join(ENIGMAPATH, 'bouquets.tv'), 'r') as f:
            for line in f:
                if line.startswith('#NAME'):
                    continue
                else:
                    if not '.suls_iptv_' in line:
                        current_bouquets_indexes.append(line)
        return current_bouquets_indexes

    def create_bouquets(self, category_order, category_options, dictchannels, multivod, allbouquet, bouquettop):
        """Create the Enigma2 bouquets
        """
        print '\n[e2m3u2bouquet]----Creating bouquets----'
        # clean old bouquets before writing new
        if dictchannels:
            for fname in os.listdir(ENIGMAPATH):
                if 'userbouquet.suls_iptv_' in fname:
                    os.remove(os.path.join(ENIGMAPATH, fname))
        iptv_bouquet_list = []

        if allbouquet:
            iptv_bouquet_list = self.create_all_channels_bouquet(category_order, category_options, dictchannels)

        vod_categories = list(cat for cat in category_order if cat.startswith('VOD -'))
        vod_category_output = False
        vod_bouquet_entry_output = False
        channel_number_start_offset_output = False

        for cat in category_order:
            if cat in dictchannels:
                cat_title = self.get_category_title(cat, category_options)
                # create file
                cat_filename = self.get_safe_filename(cat_title)

                if cat in vod_categories and not multivod:
                    cat_filename = 'VOD'
                bouquet_filepath = os.path.join(ENIGMAPATH, 'userbouquet.suls_iptv_{}.tv'.format(cat_filename))
                if DEBUG:
                    print '[e2m3u2bouquet]Creating: {}'.format(bouquet_filepath)

                if cat not in vod_categories or multivod:
                    with open(bouquet_filepath, 'w+') as f:
                        bouquet_name = 'IPTV - {}'.format(cat_title).decode('utf-8')
                        if not cat.startswith('VOD -'):
                            if cat in category_options and category_options[cat].get('nameOverride', False):
                                bouquet_name = category_options[cat]['nameOverride'].decode('utf-8')
                        else:
                            if 'VOD' in category_options and category_options['VOD'].get('nameOverride', False):
                                bouquet_name = '{} - {}'\
                                    .format(category_options['VOD']['nameOverride'].decode('utf-8'),
                                            cat_title.replace('VOD - ', '').decode("utf-8"))
                        channel_num = 0
                        f.write("#NAME {}\n".format(bouquet_name.encode("utf-8")))
                        if not channel_number_start_offset_output and not allbouquet:
                            # write place holder services (for channel numbering)
                            for i in xrange(100):
                                f.write('#SERVICE 1:832:d:0:0:0:0:0:0:0:\n')
                            channel_number_start_offset_output = True
                            channel_num += 1

                        for x in dictchannels[cat]:
                            if x['enabled']:
                                self.save_bouquet_entry(f, x)
                            channel_num += 1

                        while (channel_num % 100) is not 0:
                            f.write('#SERVICE 1:832:d:0:0:0:0:0:0:0:\n')
                            channel_num += 1
                elif not vod_category_output and not multivod:
                    # not multivod - output all the vod services in one file
                    with open(bouquet_filepath, "w+") as f:
                        bouquet_name = 'IPTV - VOD'.decode("utf-8")
                        if 'VOD' in category_options and category_options['VOD'].get('nameOverride', False):
                            bouquet_name = category_options['VOD']['nameOverride'].decode('utf-8')

                        channel_num = 0
                        f.write("#NAME {}\n".format(bouquet_name.encode("utf-8")))
                        if not channel_number_start_offset_output and not allbouquet:
                            # write place holder services (for channel numbering)
                            for i in xrange(100):
                                f.write('#SERVICE 1:832:d:0:0:0:0:0:0:0:\n')
                            channel_number_start_offset_output = True
                            channel_num += 1

                        for vodcat in vod_categories:
                            if vodcat in dictchannels:
                                # Insert group description placeholder in bouquet
                                f.write('#SERVICE 1:64:0:0:0:0:0:0:0:0:\n')
                                f.write('#DESCRIPTION {}\n'.format(vodcat))
                                for x in dictchannels[vodcat]:
                                    self.save_bouquet_entry(f, x)
                                    channel_num += 1

                                while (channel_num % 100) is not 0:
                                    f.write('#SERVICE 1:832:d:0:0:0:0:0:0:0:\n')
                                    channel_num += 1
                        vod_category_output = True

                # Add to bouquet index list
                if cat not in vod_categories or (cat in vod_categories and not vod_bouquet_entry_output):
                    iptv_bouquet_list.append(self.get_bouquet_index_name(cat_filename))
                    if cat in vod_categories and not multivod:
                        vod_bouquet_entry_output = True

        # write the bouquets.tv indexes
        self.save_bouquet_index_entries(iptv_bouquet_list, bouquettop)

        print("[e2m3u2bouquet]bouquets created ...")

    def create_all_channels_bouquet(self, category_order, category_options, dictchannels):
        """Create the Enigma2 all channels bouquet
        """
        print("\n----Creating all channels bouquet----")

        bouquet_indexes = []

        vod_categories = list(cat for cat in category_order if cat.startswith('VOD -'))
        bouquet_name = "All Channels"
        cat_filename = self.get_safe_filename(bouquet_name)

        # create file
        bouquet_filepath = os.path.join(ENIGMAPATH, 'userbouquet.suls_iptv_{}.tv'
                                        .format(cat_filename))
        if DEBUG:
            print("Creating: {}".format(bouquet_filepath))

        with open(bouquet_filepath, "w+") as f:
            f.write("#NAME IPTV - {}\n".format(bouquet_name.encode("utf-8")))

            # write place holder channels (for channel numbering)
            for i in xrange(100):
                f.write('#SERVICE 1:832:d:0:0:0:0:0:0:0:\n')
            channel_num = 1

            for cat in category_order:
                if cat in dictchannels:
                    if cat not in vod_categories:
                        cat_title = self.get_category_title(cat, category_options)
                        # Insert group description placeholder in bouquet
                        f.write("#SERVICE 1:64:0:0:0:0:0:0:0:0:\n")
                        f.write("#DESCRIPTION {}\n".format(cat_title))
                        for x in dictchannels[cat]:
                            if x['enabled']:
                                self.save_bouquet_entry(f, x)
                            channel_num += 1

                        while (channel_num % 100) is not 0:
                            f.write('#SERVICE 1:832:d:0:0:0:0:0:0:0:\n')
                            channel_num += 1

        # Add to bouquet index list
        bouquet_indexes.append(self.get_bouquet_index_name(cat_filename))
        print("all channels bouquet created ...")
        return bouquet_indexes

    def save_bouquet_entry(self, f, channel):
        """Add service to bouquet file
        """
        f.write('#SERVICE {}:{}:{}\n'.format(channel['serviceRef'], channel['stream-url'].replace(':', '%3a'), self.get_service_title(channel).encode('utf-8')))
        f.write('#DESCRIPTION {}\n'.format(self.get_service_title(channel).encode('utf-8')))

    def get_bouquet_index_name(self, filename):
        return ('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.suls_iptv_{}.tv" ORDER BY bouquet\n'
                .format(filename))

    def save_bouquet_index_entries(self, iptv_bouquets, bouquettop):
        """Add to the main bouquets.tv file
        """
        # get current bouquets indexes
        current_bouquet_indexes = self.get_current_bouquet_indexes()

        if iptv_bouquets:
            with open(os.path.join(ENIGMAPATH, 'bouquets.tv'), 'w') as f:
                f.write('#NAME Bouquets (TV)\n')
                if bouquettop:
                    for bouquet in iptv_bouquets:
                        f.write(bouquet)
                    for bouquet in current_bouquet_indexes:
                        f.write(bouquet)
                else:
                    for bouquet in current_bouquet_indexes:
                        f.write(bouquet)
                    for bouquet in iptv_bouquets:
                        f.write(bouquet)

    def reload_bouquets(self):
        if not TESTRUN:
            print '\n[e2m3u2bouquet]----Reloading bouquets----'
            os.system('wget -qO - http://127.0.0.1/web/servicelistreload?mode=2 > /dev/null 2>&1 &')
            print '[e2m3u2bouquet]bouquets reloaded...'

    def create_epgimporter_config(self, categoryorder, category_options, dictchannels, list_xmltv_sources, epgurl, provider):
        indent = '  '
        if DEBUG:
            print '[e2m3u2bouquet]creating EPGImporter config'
        # create channels file
        if not os.path.isdir(EPGIMPORTPATH):
            os.makedirs(EPGIMPORTPATH)
        channels_filename = os.path.join(EPGIMPORTPATH, 'suls_iptv_channels.xml')

        if dictchannels:
            with open(channels_filename, "w+") as f:
                f.write('<channels>\n')
                for cat in categoryorder:
                    if cat in dictchannels:
                        if not cat.startswith('VOD'):
                            cat_title = self.get_category_title(cat, category_options)

                            f.write('{}<!-- {} -->\n'.format(indent, self.xml_escape(cat_title.encode('utf-8'))))
                            for x in dictchannels[cat]:
                                tvg_id = x['tvg-id'] if x['tvg-id'] else self.get_service_title(x)
                                if x['enabled']:
                                    f.write('{}<channel id="{}">{}:http%3a//example.m3u8</channel> <!-- {} -->\n'
                                            .format(indent, self.xml_escape(tvg_id.encode('utf-8')), x['serviceRef'],
                                                    self.xml_escape(self.get_service_title(x).encode('utf-8'))))
                f.write("</channels>\n")

            # create epg-importer sources file for providers feed
            self.create_epgimport_source([epgurl], provider)

            # create epg-importer sources file for additional feeds
            for group in list_xmltv_sources:
                self.create_epgimport_source(list_xmltv_sources[group], '{} - {}'.format(provider, group))

    def create_epgimport_source(self, sources, source_name):
        """Create epg-importer source file
        """
        indent = '  '
        channels_filename = os.path.join(EPGIMPORTPATH, 'suls_iptv_channels.xml')
        source_filename = os.path.join(EPGIMPORTPATH, 'suls_iptv_{}.sources.xml'.format(self.get_safe_filename(source_name)))
        with open(os.path.join(EPGIMPORTPATH, source_filename), 'w+') as f:
            f.write('<sources>\n')
            f.write('{}<source type="gen_xmltv" channels="{}">\n'.format(indent, channels_filename))
            f.write('{}<description>{}</description>\n'.format(2 * indent, self.xml_escape(source_name)))
            for source in sources:
                f.write('{}<url>{}</url>\n'.format(2 * indent, self.xml_escape(source)))

            f.write('{}</source>\n'.format(indent))
            f.write('</sources>\n')

    def read_providers(self, providerfile):
        # Check we have data
        try:
            if not os.path.getsize(providerfile):
                raise Exception, 'Providers file is empty'
        except Exception as e:
            raise e

        f = open(providerfile, 'r')
        for line in f:
            if line == '400: Invalid request\n':
                print '[e2m3u2bouquet]Providers download is invalid please resolve or use URL based setup'
                sys(exit(1))
            line = base64.b64decode(line)
            if line:
                provider = {
                    'name': line.split(',')[0],
                    'm3u': line.split(',')[1],
                    'epg': line.split(',')[2]
                }
            PROVIDERS[provider['name']] = provider

        f.close()
        return PROVIDERS

    def process_provider(self, provider, username, password):
        supported_providers = ''
        for line in PROVIDERS:
            supported_providers += ' ' + PROVIDERS[line]['name']
            if PROVIDERS[line]['name'].upper() == provider.upper():
                if DEBUG:
                    print '[e2m3u2bouquet]----Provider setup details----'
                    print 'm3u = ' + PROVIDERS[line]['m3u'].replace('USERNAME', username).replace('PASSWORD', password)
                    print 'epg = ' + PROVIDERS[line]['epg'].replace('USERNAME', username).replace('PASSWORD', password) + '\n'
                return (PROVIDERS[line]['m3u'].replace('USERNAME', username).replace('PASSWORD', password),
                 PROVIDERS[line]['epg'].replace('USERNAME', username).replace('PASSWORD', password),
                 supported_providers)
        # If we get here the supplied provider is invalid
        return ('NOTFOUND', '', 0, 0, 0, 0, supported_providers)

    def get_mapping_file(self):
        mapping_file = None
        search_path = [os.path.join(CFGPATH, 'e2m3u2bouquet-sort-override.xml'),
                       os.path.join(os.getcwd(), 'e2m3u2bouquet-sort-override.xml')]
        for path in search_path:
            if os.path.isfile(path):
                mapping_file = path
                break;
        return mapping_file

    def xml_escape(self, string):
        return string.replace('&', '&amp;').replace('"', '&quot;').replace("'", '&apos;').replace('<', '&lt;').replace('>', '&gt;')

    def xml_unescape(self, string):
        return string.replace('&quot;', '"').replace().replace('&apos;', "'").replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

    def get_service_title(self, channel):
        """Return the title override if set else the title
        """
        if channel.get('nameOverride', False):
            return channel['nameOverride']
        return channel['stream-name']

    def get_category_title(self, cat, category_options):
        """Return the title override if set else the title
        """
        if cat in category_options:
            if category_options[cat].get('nameOverride', False):
                return category_options[cat]['nameOverride']
            return cat
        return cat

    def get_category_id(self, cat):
        """Generate 32 bit category id to help make service refs unique"""
        return hashlib.md5(cat).hexdigest()[:8]


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)
    try:
        # Setup argument parser
	parser = ArgumentParser(description='IPTVBouquet', formatter_class=RawDescriptionHelpFormatter)
        urlgroup = parser.add_argument_group('URL Based Setup')
        urlgroup.add_argument('-m', '--m3uurl', dest='m3uurl', action='store', help='URL to download m3u data from (required)')
        urlgroup.add_argument('-e', '--epgurl', dest='epgurl', action='store', help='URL source for XML TV epg data sources')
        # Provider based setup
        providergroup = parser.add_argument_group('Provider Based Setup')
        providergroup.add_argument('-n', '--providername', dest='providername', action='store', help='Host IPTV provider name (FAB/EPIC) (required)')
        providergroup.add_argument('-u', '--username', dest='username', action='store', help='Your IPTV username (required)')
        providergroup.add_argument('-p', '--password', dest='password', action='store', help='Your IPTV password (required)')
        parser.add_argument('-i', '--iptvtypes', dest='iptvtypes', action='store_true', help='Treat all stream references as IPTV stream type. (required for some enigma boxes)')
        parser.add_argument('-M', '--multivod', dest='multivod', action='store_true', help='Create multiple VOD bouquets rather single VOD bouquet')
        parser.add_argument('-a', '--allbouquet', dest='allbouquet', action='store_true', help='Create all channels bouquet')
        parser.add_argument('-P', '--picons', dest='picons', action='store_true', help='Automatically download of Picons, this option will slow the execution')
        parser.add_argument('-q', '--iconpath', dest='iconpath', action='store', help='Option path to store picons, if not supplied defaults to /usr/share/enigma2/picon/')
        parser.add_argument('-xs', '--xcludesref', dest='xcludesref', action='store_true', help='Disable service ref overriding from override.xml file')
        parser.add_argument('-b', '--bouqueturl', dest='bouqueturl', action='store', help='URL to download providers bouquet - to map custom service references')
        parser.add_argument('-bd', '--bouquetdownload', dest='bouquetdownload', action='store_true', help='Download providers bouquet (use default url) - to map custom service references')
        parser.add_argument('-bt', '--bouquettop', dest='bouquettop', action='store_true', help='Place IPTV bouquets at top')
        parser.add_argument('-U', '--uninstall', dest='uninstall', action='store_true', help='Uninstall all changes made by this script')
        parser.add_argument('-D', '--deleteP', dest='deleteP', action='store_true', help='Replace Saved Prodiders file')
        args = parser.parse_args()
        m3uurl = args.m3uurl
        epgurl = args.epgurl
        iptvtypes = args.iptvtypes
        uninstall = args.uninstall
        multivod = args.multivod
        allbouquet = args.allbouquet
        bouquet_url = args.bouqueturl
        bouquet_download = args.bouquetdownload
        picons = args.picons
        iconpath = args.iconpath
        xcludesref = args.xcludesref
        bouquettop = args.bouquettop
        provider = args.providername
        username = args.username
        password = args.password
	deleteP = args.deleteP
        # Set epg to rytec if nothing else provided
        if epgurl is None:
            epgurl = 'http://www.vuplus-community.net/rytec/rytecxmltv-UK.gz'
        # Set piconpath
        if iconpath is None:
            iconpath = PICONSPATH
        if provider is None:
            provider = 'E2m3u2Bouquet'
        # Check we have enough to proceed
        if m3uurl is None and (provider is None or username is None or password is None) and uninstall is False:
            print '[e2m3u2bouquet]Please ensure correct command line options are passed to the program, for help use --help\n'
            parser.print_usage()
            sys.exit(1)

    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except Exception as e:
        if DEBUG or TESTRUN:
            raise e
        return 2

    # # Core program logic starts here
    e2m3uSetup = IPTVSetup()
    print '[e2m3u2bouquet]  Core program logic starts here...'
    if uninstall:
        # Clean up any existing files
        e2m3uSetup.uninstaller()
        # reload bouquets
        e2m3uSetup.reload_bouquets()
        print '[e2m3u2bouquet]Uninstall only, program exiting ...'
        sys.exit(1)  # Quit here if we just want to uninstall
    else:
        # create e2m3u2bouquet config folder if it doesn't exist
        if not os.path.isdir(CFGPATH):
            os.makedirs(CFGPATH)
	    deleteP = True	

        # Work out provider based setup if that's what we have

        if provider is not None and username is not None or password is not None:
	    providersfile = os.path.join(CFGPATH, 'IPTVcreate_providers.txt')
            print '\n[e2m3u2bouquet]----Setup for Saved providers file'
	    if deleteP:
            	print '\n[e2m3u2bouquet]----Delete saved file_ Downloading Online providers file'
		providersfile = e2m3uSetup.download_providers(PROVIDERSURL)
	    elif not os.path.isfile(providersfile):
        		print '\n[e2m3u2bouquet]----Downloading Online providers file----'
			providersfile = e2m3uSetup.download_providers(PROVIDERSURL)
            e2m3uSetup.read_providers(providersfile)
            m3uurl, epgurl, supported_providers = e2m3uSetup.process_provider(provider, username, password)
            if m3uurl == 'NOTFOUND':
                print '----ERROR----'
                print '[e2m3u2bouquet]Provider not found, supported providers = ' + supported_providers
                sys(exit(1))

        # get default provider bouquet download url if bouquet download set and no bouquet url given
        if bouquet_download and not bouquet_url:
            # set bouquet_url to default url
            pos = m3uurl.find('get.php')
            if pos != -1:
                bouquet_url = m3uurl[0:pos + 7] + '?username={}&password={}&type=dreambox&output=ts'.format(
                    username, password)
        # Download panel bouquet
        panel_bouquet = None
        if bouquet_url:
            panel_bouquet_file = e2m3uSetup.download_bouquet(bouquet_url)
            panel_bouquet = e2m3uSetup.parse_panel_bouquet(panel_bouquet_file)
        # Download m3u
        m3ufile = e2m3uSetup.download_m3u(m3uurl)
        # parse m3u file
        categoryorder, category_options, dictchannels = e2m3uSetup.parse_m3u(m3ufile, iptvtypes, panel_bouquet, xcludesref)
        list_xmltv_sources = e2m3uSetup.parse_map_xmltvsources_xml()
        # save xml mapping - should be after m3u parsing
        e2m3uSetup.save_map_xml(categoryorder, category_options, dictchannels, list_xmltv_sources)

        #download picons
        if picons:
            e2m3uSetup.download_picons(dictchannels, iconpath)
        # Create bouquet files
        e2m3uSetup.create_bouquets(categoryorder, category_options, dictchannels, multivod, allbouquet, bouquettop)
        # Now create custom channels for each bouquet
        print '\n[e2m3u2bouquet]----Creating EPG-Importer config ----'
        e2m3uSetup.create_epgimporter_config(categoryorder, category_options, dictchannels, list_xmltv_sources, epgurl, provider)
        print '[e2m3u2bouquet]EPG-Importer config created...'
        # reload bouquets
        e2m3uSetup.reload_bouquets()
	sortfile = os.path.join(CFGPATH + 'e2m3u2bouquet-sort-override.bak')
	if os.path.isfile(sortfile):		
		os.remove(sortfile)
	sortfile = os.path.join(CFGPATH + 'e2m3u2bouquet-sort-override.xml')
	if os.path.isfile(sortfile):
        	os.rename(CFGPATH + 'e2m3u2bouquet-sort-override.xml', CFGPATH + 'e2m3u2bouquet-sort-override.bak')
        	os.rename(CFGPATH + 'e2m3u2bouquet-sort-current.xml', CFGPATH + 'e2m3u2bouquet-sort-override.xml')
        print '\n********************************'
        print 'Engima2 IPTV bouquets created ! '
        print '********************************'
        print '\nTo enable EPG data'
        print 'Please open EPG-Importer plugin.. '
        print 'Select sources and enable the new IPTV sources (will be listed as {})'.format(provider)
        print 'Save the selected sources, press yellow button to start manual import'
        print 'You can then set EPG-Importer to automatically import the EPG every day'
    return


if __name__ == '__main__':
    if TESTRUN:
        EPGIMPORTPATH = 'H:/Satelite Stuff/epgimport/'
        ENIGMAPATH = 'H:/Satelite Stuff/enigma2/'
        PICONSPATH = 'H:/Satelite Stuff/picons/'
    sys.exit(main())
