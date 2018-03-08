import os
import sys
from time import localtime, time, strftime, mktime, asctime
from enigma import eTimer
import unicodedata
import datetime
from PIL import Image
from . import _, PluginLanguageDomain
import Components.Task
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.SelectionList import SelectionList, SelectionEntryComponent
from Components.ScrollLabel import ScrollLabel
from Components.Button import Button
from Components.MenuList import MenuList
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock, ConfigEnableDisable, getConfigListEntry, ConfigSubDict, ConfigPassword, ConfigSelectionNumber
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Screens.Setup import Setup
from Components.Console import Console
from Screens.Console import Console as ScreenConsole
from Screens.MessageBox import MessageBox
from Tools.Notifications import AddPopupWithCallback
import e2m3u2bouquet
autoStartTimer = None
_session = None

def get_providers_list():
    	iptv = e2m3u2bouquet.IPTVSetup()
	if os.path.isdir(e2m3u2bouquet.CFGPATH):
		filename = os.path.join(e2m3u2bouquet.CFGPATH, 'IPTVcreate_providers.txt')
		providers =iptv.read_providers(filename)
    	else:
		providers = iptv.read_providers(iptv.download_providers(e2m3u2bouquet.PROVIDERSURL))
    	return sorted(providers.keys())

config.IPTVcreate = ConfigSubsection()
config.IPTVcreate.Provname = ConfigSelection(default='ACE', choices=get_providers_list())
config.IPTVcreate.Username = ConfigText(default = "", fixed_size=False)
config.IPTVcreate.Password = ConfigPassword(default='', fixed_size=False)
config.IPTVcreate.Provname2 = ConfigSelection(default='FAB', choices=get_providers_list())
config.IPTVcreate.Username2 = ConfigText(default = "", fixed_size=False)
config.IPTVcreate.Password2 = ConfigPassword(default='', fixed_size=False)
config.IPTVcreate.Piconpath = ConfigSelection(default='/usr/share/enigma2/picon/', choices=[
 '/usr/share/enigma2/picon/',
 '/media/usb/picon/',
 '/media/hdd/picon/'])
config.IPTVcreate.Picon = ConfigYesNo(default = False)
config.IPTVcreate.Uninstall = ConfigYesNo(default = False)
config.IPTVcreate.Multivod = ConfigYesNo(default = False)
config.IPTVcreate.bouquetpos = ConfigSelection(default='bottom', choices=[
 'bottom', 'top'])
config.IPTVcreate.bouquetdownload = ConfigEnableDisable(default=False)
config.IPTVcreate.AllBouquet = ConfigYesNo(default = False)
config.IPTVcreate.Xcludesref = ConfigYesNo(default = False)
config.IPTVcreate.iptvtypes = ConfigEnableDisable(default=False)
config.IPTVcreate.autobouquetupdateatboot = ConfigYesNo(default=False)
config.IPTVcreate.autobouquetupdate = ConfigYesNo(default=False)
config.IPTVcreate.updateinterval = ConfigSelectionNumber(default=6, min=2, max=48, stepwidth=1)
config.IPTVcreate.last_update = ConfigNumber(default=0)

class IPTVcreate(Screen):
	skin = """<screen name="IPTVcreate" position="center,center" size="560,400" title="IPTVcreate">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/key_menu.png" position="0,40" size="35,25" alphatest="blend" transparent="1" zPosition="3"/>
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget name="cancel" position="22,1032" size="400,39" foregroundColor="grey" zPosition="1" font="Regular;33" halign="center"/>
		<widget name="ok" position="457,1032" size="400,39" foregroundColor="grey" zPosition="1" font="Regular;33" halign="center"/>
		<widget name="lab1" render="Label" position="100,700" size="580,200" halign="center" valign="center" font="Regular; 30" />
		<widget name="statusbar" position="10,410" size="500,20" font="Regular;18" />
		<applet type="onLayoutFinish">
		</applet>
	</screen>"""

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle = _("IPTVcreate")
		self.menu_path = menu_path
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			condtext = ""
			if self.menu_path and not self.menu_path.endswith(' / '):
				condtext = self.menu_path + " >"
			elif self.menu_path:
				condtext = self.menu_path[:-3] + " >"
			self["menu_path_compressed"] = StaticText(condtext)
			self.menu_path += screentitle + ' / '
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		print "[IPTVcreate] Start Enabled"
		self['statusbar'] = Label()
        	self.update_status()
		self.Config_List()
                self.session = session
		self.Console = Console()
		self.Prov = 1
		
		
	def Config_List(self):
            	print "[IPTVcreate] Display Menu"
		self["key_red"] = Button(_("Exit"))
		self["key_green"] = Button(_("Setup"))
		self["key_yellow"] = Button("Run")
		self["key_blue"] = Button("ProvSwitch")
		self['lab1'] = Label(_("Select Green button to set Config settings:\n Yellow button to download latest IPTV Bouquets"))
		self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "HelpActions"],
									  {
									  'cancel': self.close,
									  'red': self.close,
									  'green': self.createSetup,
									  'yellow': self.manual_update,
									  'blue': self.Provswitch,
									  "menu": self.createSetup,
									  "ok": self.close,
									  }, -1)
                                                                              
                
       	def createSetup(self):
            	print "[IPTVcreate] Update Config"
		self.session.openWithCallback(self.configOK, Setup, 'IPTVcreate', 'SystemPlugins/ViX', self.menu_path, PluginLanguageDomain)
                 
	def configOK(self, test=None):
            	print "[IPTVcreate] Config OK"
        	self.provider = config.IPTVcreate.Provname.value
        	self.username = config.IPTVcreate.Username.value 
        	self.password = config.IPTVcreate.Password.value
        	self.Piconpath = config.IPTVcreate.Piconpath.value
        	self.multivod = config.IPTVcreate.Multivod.value
        	self.xcludesref = config.IPTVcreate.Xcludesref.value
        	self.iptvtypes = config.IPTVcreate.iptvtypes.value

	def Provswitch(self):
		self.Prov = 2
		self.do_mainupdate(0)
		

    	def manual_update(self):
        	self.session.openWithCallback(self.manual_update_callback, MessageBox, _('Start Channels Update with saved Providers?'), MessageBox.TYPE_YESNO, timeout=15, default=True)

    	def manual_update_callback(self, confirmed):
        	if not confirmed:
			self.do_mainupdate(1)
                else:
			self.do_mainupdate(0)

	def do_mainupdate(self, ret):
		if config.IPTVcreate.Provname.value:
			sys.argv = []
			if self.Prov == 1:
				sys.argv.append('-n={}'.format(config.IPTVcreate.Provname.value))
				sys.argv.append('-u={}'.format(config.IPTVcreate.Username.value))
				sys.argv.append('-p={}'.format(config.IPTVcreate.Password.value))
			else:
				sys.argv.append('-n={}'.format(config.IPTVcreate.Provname2.value))
				sys.argv.append('-u={}'.format(config.IPTVcreate.Username2.value))
				sys.argv.append('-p={}'.format(config.IPTVcreate.Password2.value))
			if config.IPTVcreate.iptvtypes.value:
			    sys.argv.append('-i')
			if config.IPTVcreate.Multivod.value:
			    sys.argv.append('-M')
			if config.IPTVcreate.AllBouquet.value:
			    sys.argv.append('-a')
			if config.IPTVcreate.Picon.value:
			    sys.argv.append('-P')
			    sys.argv.append('-q={}'.format(config.IPTVcreate.Piconpath.value))
			if config.IPTVcreate.Xcludesref.value:
			    sys.argv.append('-xs')
			if config.IPTVcreate.bouquetpos.value and config.IPTVcreate.bouquetpos.value == 'top':
			    sys.argv.append('-bt')
			if config.IPTVcreate.bouquetdownload.value:
			    sys.argv.append('-bd')
			if config.IPTVcreate.Uninstall.value:
			    sys.argv.append('-U')
			if ret == 1:
			    sys.argv.append('-D')
			print "[IPTVcreate] Start Manual IPTV Import Enabled"
			e2m3u2bouquet.main(sys.argv)
			print "[IPTVcreate] Manual IPTV Import Complete"
			config.IPTVcreate.last_update.value = int(time())
			config.IPTVcreate.last_update.save()
        		self.update_status()

	def update_status(self):
		print "[IPTVcreate] Update status %s" % (config.IPTVcreate.last_update.value) 
	  	if config.IPTVcreate.last_update.value != 0:
			t = localtime(config.IPTVcreate.last_update.value)
			updatetext = _("Last channel update: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			updatetext = _("First channel update: ")
		self['statusbar'].setText(str(updatetext))

class AutoStartTimer:

	def __init__(self, session):
		self.session = session
		self.timer = eTimer()
		self.timer.callback.append(self.on_timer)
		self.update()

	def get_wake_time(self):
		print "[IPTVcreate] AutoStartTimer -> get_wake_time"
		if config.IPTVcreate.autobouquetupdate.value and config.IPTVcreate.updateinterval.value:
		    interval = int(config.IPTVcreate.updateinterval.value)
		    nowt = time()
		    return int(nowt) + interval * 60 * 60
		else:
		    return -1

	def update(self, atLeast=0):
		print "[IPTVcreate] AutoStartTimer -> update"
		self.timer.stop()
		wake = self.get_wake_time()
		nowt = time()
		now = int(nowt)
		print "[IPTVcreate] wake {} now {}".format(wake, now)
		if wake > 0:
		    next = wake - now
		    self.timer.startLongTimer(next)
		else:
		    wake = -1
		return wake

	def on_timer(self):
		self.timer.stop()
		now = int(time())
		print "[IPTVcreate] on_timer occured at {}".format(now)
		print "[IPTVcreate] Starting bouquet update because auto update bouquet schedule is enabled"
		do_update()
		self.update()

	def get_status(self):
		print "[IPTVcreate] AutoStartTimer -> getStatus"


def do_update():
    if config.IPTVcreate.Provname.value:
	sys.argv = []
	sys.argv.append('-n={}'.format(config.IPTVcreate.Provname.value))
	sys.argv.append('-u={}'.format(config.IPTVcreate.Username.value))
	sys.argv.append('-p={}'.format(config.IPTVcreate.Password.value))
	if config.IPTVcreate.iptvtypes.value:
	    sys.argv.append('-i')
	if config.IPTVcreate.Multivod.value:
	    sys.argv.append('-M')
	if config.IPTVcreate.allbouquet.value:
	    sys.argv.append('-a')
	if config.IPTVcreate.Picon.value:
	    sys.argv.append('-P')
	    sys.argv.append('-q={}'.format(config.IPTVcreate.Piconpath.value))
	if config.IPTVcreate.Xcludesref.value:
	    sys.argv.append('-xs')
        if config.IPTVcreate.bouquetpos.value and config.IPTVcreate.bouquetpos.value == 'top':
            sys.argv.append('-bt')
        if config.IPTVcreate.bouquetdownload.value:
            sys.argv.append('-bd')
	if config.IPTVcreate.Uninstall.value:
	    sys.argv.append('-U')
	print "[IPTVcreate] Start Timer IPTV Import Enabled"
	e2m3u2bouquet.main(sys.argv)
	print "[IPTVcreate] Timer IPTV Import Complete"
	config.IPTVcreate.last_update.value = int(time())
	config.IPTVcreate.last_update.save()


def main(session, **kwargs):
    print "[IPTVcreate] Timer main"
    session.openWithCallback(done_configuring, IPTVcreate)


def done_configuring():
    """Check for new config values for auto start
    """
    global autoStartTimer
    print "[IPTVcreate] Done configuring"
    if autoStartTimer is not None:
	autoStartTimer.update()
    return


def on_boot_start_check():
    """This will only execute if the
    config option autobouquetupdateatboot is true
    """
    now = int(time())
    print "[IPTVcreate] Starting bouquet update because auto update bouquet at start enabled"
    do_update()


def IPTVcreateautostart(reason, session=None, **kwargs):
    global autoStartTimer
    global _session
    print "[IPTVcreate] autostart {} occured at {}".format(reason, time())
    if reason == 0 and _session is None:
	if session is not None:
	    _session = session
	    if autoStartTimer is None:
	        autoStartTimer = AutoStartTimer(session)
	    if config.IPTVcreate.autobouquetupdateatboot.value:
	        on_boot_start_check()
    return


def get_next_wakeup():
    print "[IPTVcreate] get_next_wakeup"
    return -1

