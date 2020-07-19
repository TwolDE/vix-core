from __future__ import print_function, absolute_import

# for localized messages
from os import listdir, path, walk, stat
from boxbranding import getBoxType, getImageDistro

from src import _

from Components.config import config, ConfigBoolean, configfile
from Plugins.Plugin import PluginDescriptor

from src.BackupManager import BackupManagerautostart
from src.ImageManager import ImageManagerautostart
from src.IPKInstaller import IpkgInstaller
from src.SoftcamManager import SoftcamAutostart

config.misc.restorewizardrun = ConfigBoolean(default=False)

def setLanguageFromBackup(backupfile):
	try:
		print(backupfile)
		import tarfile
		tar = tarfile.open(backupfile)
		for member in tar.getmembers():
			if member.name == "etc/enigma2/settings":
				for line in tar.extractfile(member):
					if line.startswith("config.osd.language"):
						print(line)
						languageToSelect = line.strip().split("=")[1]
						print(languageToSelect)
						if languageToSelect:
							from Components.Language import language
							language.activateLanguage(languageToSelect)
							break
		tar.close()
	except:
		pass

def checkConfigBackup():
	try:
		devmounts = []
		list = []
		files = []
		for dir in ["/media/%s/backup" % media for media in listdir("/media/") if path.isdir(path.join("/media/", media))]:
			devmounts.append(dir)
		if len(devmounts):
			for devpath in devmounts:
				if path.exists(devpath):
					try:
						files = listdir(devpath)
					except:
						files = []
				else:
					files = []
				if len(files):
					for file in files:
						if file.endswith(".tar.gz") and "vix" in file.lower():
							list.append((path.join(devpath, file)))
 		if len(list):
			print("[RestoreWizard] Backup Image:", list[0])
			backupfile = list[0]
			if path.isfile(backupfile):
				setLanguageFromBackup(backupfile)
			return True
		else:
			return None
	except IOError as e:
		print("[ViX] unable to use device (%s)..." % str(e))
		return None

if config.misc.firstrun.value and not config.misc.restorewizardrun.value:
	if checkConfigBackup() is None:
		backupAvailable = 0
	else:
		backupAvailable = 1


def VIXMenu(session):
	from src import ui
	return ui.VIXMenu(session)

def UpgradeMain(session, **kwargs):
	session.open(VIXMenu)

def startSetup(menuid):
	if menuid != "setup":
		return []
	return [(_("ViX"), UpgradeMain, "vix_menu", 1010)]

def RestoreWizard(*args, **kwargs):
	from src.RestoreWizard import RestoreWizard
	return RestoreWizard(*args, **kwargs)

def SoftcamManager(session):
	from src.SoftcamManager import VIXSoftcamManager
	return VIXSoftcamManager(session)

def SoftcamMenu(session, **kwargs):
	session.open(SoftcamManager)

def SoftcamSetup(menuid):
	if menuid == "cam":
		return [(_("Softcam manager"), SoftcamMenu, "softcamsetup", 1005)]
	return []

def BackupManager(session):
	from src.BackupManager import VIXBackupManager
	return VIXBackupManager(session)

def BackupManagerMenu(session, **kwargs):
	session.open(BackupManager)

def ImageManager(session):
	from src.ImageManager import VIXImageManager
	return VIXImageManager(session)

def ImageMangerMenu(session, **kwargs):
	session.open(ImageManager)

def H9SDmanager(session):
	from src.H9SDmanager import H9SDmanager
	return H9SDmanager(session)

def H9SDmanagerMenu(session, **kwargs):
	session.open(H9SDmanager)

def MountManager(session):
	from src.MountManager import VIXDevicesPanel
	return VIXDevicesPanel(session)

def MountManagerMenu(session, **kwargs):
	session.open(MountManager)

def filescan_open(list, session, **kwargs):
	filelist = [x.path for x in list]
	session.open(IpkgInstaller, filelist)  # list

def filescan(**kwargs):
	from Components.Scanner import Scanner, ScanPath
	return Scanner(mimetypes=["application/x-debian-package"],
				paths_to_scan=
				[
					ScanPath(path="ipk", with_subdirs=True),
					ScanPath(path="", with_subdirs=False),
				],
				name="Ipkg",
				description=_("Install extensions."),
				openfnc=filescan_open)


def Plugins(**kwargs):
	plist = [PluginDescriptor(where=PluginDescriptor.WHERE_MENU, needsRestart=False, fnc=startSetup),
			 PluginDescriptor(name=_("ViX Image Management"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=UpgradeMain),
			 PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SoftcamSetup)]
	if config.softcammanager.showinextensions.value:
		plist.append(PluginDescriptor(name=_("Softcam manager"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=SoftcamMenu))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=SoftcamAutostart))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=ImageManagerautostart))
	plist.append(PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=BackupManagerautostart))
	if config.misc.firstrun.value and not config.misc.restorewizardrun.value and backupAvailable == 1:
		plist.append(PluginDescriptor(name=_("Restore wizard"), where=PluginDescriptor.WHERE_WIZARD, needsRestart=False, fnc=(0, RestoreWizard)))
	plist.append(PluginDescriptor(name=_("Ipkg"), where=PluginDescriptor.WHERE_FILESCAN, needsRestart=False, fnc=filescan))
	plist.append(PluginDescriptor(name=_("ViX Backup manager"), where=PluginDescriptor.WHERE_VIXMENU, fnc=BackupManagerMenu))
	plist.append(PluginDescriptor(name=_("ViX Image manager"), where=PluginDescriptor.WHERE_VIXMENU, fnc=ImageMangerMenu))
	return plist
