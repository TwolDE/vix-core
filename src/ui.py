# for localized messages
from os import listdir, path, mkdir

from . import _
from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Screens.ParentalControlSetup import ProtectedScreen
from Components.config import config
from Components.SystemInfo import SystemInfo

class VIXMenu(Screen, ProtectedScreen):
	skin = """
		<screen name="VIXMenu" position="center,center" size="610,410">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
			<widget source="menu" render="Listbox" position="15,60" size="330,290" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (2,2), size = (330,24), flags = RT_HALIGN_LEFT, text = 1), # index 0 is the MenuText,
						],
					"fonts": [gFont("Regular",22)],
					"itemHeight":25
					}
				</convert>
			</widget>
			<widget source="menu" render="Listbox" position="360,50" size="240,300" scrollbarMode="showNever" selectionDisabled="1">
				<convert type="TemplatedMultiContent">
					{"template": [
							MultiContentEntryText(pos = (2,2), size = (240,300), flags = RT_HALIGN_CENTER|RT_VALIGN_CENTER|RT_WRAP, text = 2), # index 2 is the Description,
						],
					"fonts": [gFont("Regular",22)],
					"itemHeight":300
					}
				</convert>
			</widget>
			<widget source="status" render="Label" position="5,360" zPosition="10" size="600,50" halign="center" valign="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		</screen>"""

	def __init__(self, session, args=0):
		Screen.__init__(self, session)
		ProtectedScreen.__init__(self)
		screentitle = _("ViX")
		self.menu_path = _("Main menu")+' / '+_("Setup")+' / '
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
		self.menu = args
		self.list = []
		if self.menu == 0:
			self.list.append(("backup-manager", _("Backup settings"), _("Manage settings backup."), None))
			self.list.append(("image-manager", _("ViX Image Manager"), _("Backup/Flash/ReBoot system image."), None))
			self.list.append(("ipkg-install", _("Install local extension"), _("Install IPK's from your tmp folder."), None))
			self.list.append(("mount-manager", _("Mount manager"), _("Manage your devices mount points."), None))
			self.list.append(("IPTV-manager", _("IPTV Bouquet manager"), _("Manage your IPTV Bouquets"), None))
		if self.menu == 0 and SystemInfo["HaveMultiBoot"]:
			self.list.append(("ImageFlash", _("MultiBoot-Image flash"), _("Couch flash any Arm EMMC partition."), None))
			self.list.append(("ImageBackup", _("HDD/USB Image backup"), _("Backup to HDD or USB."), None))
			self.list.append(("MultiBoot", _("Select MultiBoot Image to Reboot"), _("Boot from any MultiBoot Image Partition."), None))
		self["menu"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))

		self["shortcuts"] = NumberActionMap(["ShortcutActions", "WizardActions", "InfobarEPGActions", "MenuActions", "NumberActions"],
											{
											"ok": self.go,
											"back": self.close,
											"red": self.close,
											"menu": self.closeRecursive,
											"1": self.go,
											"2": self.go,
											"3": self.go,
											"4": self.go,
											"5": self.go,
											"6": self.go,
											"7": self.go,
											"8": self.go,
											"9": self.go,
											}, -1)
		self.onLayoutFinish.append(self.layoutFinished)
		self.onChangedEntry = []
		self["menu"].onSelectionChanged.append(self.selectionChanged)

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and config.ParentalControl.config_sections.vixmenu.value
	
	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary

		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["menu"].getCurrent()
		if item:
			name = item[1]
			desc = item[2]
		else:
			name = "-"
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def layoutFinished(self):
		idx = 0
		self["menu"].index = idx

	def go(self, num=None):
		if num is not None:
			num -= 1
			if not num < self["menu"].count():
				return
			self["menu"].setIndex(num)
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if self.menu == 0:
				if currentEntry == "backup-manager":
					from BackupManager import VIXBackupManager
					self.session.open(VIXBackupManager, self.menu_path)
				elif currentEntry == "image-manager":
					from ImageManager import VIXImageManager
					self.session.open(VIXImageManager, self.menu_path)
				elif currentEntry == "ipkg-install":
					from IPKInstaller import VIXIPKInstaller
					self.session.open(VIXIPKInstaller, self.menu_path)
				elif currentEntry == "mount-manager":
					from MountManager import VIXDevicesPanel
					self.session.open(VIXDevicesPanel, self.menu_path)
				elif currentEntry == "IPTV-manager":
					from IPTVcreate import IPTVcreate
					self.session.open(IPTVcreate, self.menu_path)
				elif currentEntry == "ImageFlash":
					from ImageFlash import ImageFlash
					self.session.open(ImageFlash, self.menu_path)
				elif currentEntry == "ImageBackup":
					from ImageBackup import ImageBackup
					self.session.open(ImageBackup, self.menu_path)
				elif currentEntry == "MultiBoot":
					from MultiBoot import MultiBoot
					self.session.open(MultiBoot, self.menu_path)

	def closeRecursive(self):
		self.close(True)
