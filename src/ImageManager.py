# for localized messages
from boxbranding import getBoxType, getImageType, getImageDistro, getImageVersion, getImageBuild, getImageDevBuild, getImageFolder, getImageFileSystem, getBrandOEM, getMachineBrand, getMachineName, getMachineBuild, getMachineMake, getMachineMtdRoot, getMachineRootFile, getMachineMtdKernel, getMachineKernelFile, getMachineMKUBIFS, getMachineUBINIZE
from os import path, stat, system, mkdir, makedirs, listdir, remove, rename, statvfs, chmod, walk, symlink, unlink
from shutil import rmtree, move, copy, copyfile
from time import localtime, time, strftime, mktime
import urllib

from enigma import eTimer, fbClass

from . import _, PluginLanguageDomain
import Tools.CopyFiles
import Components.Task
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.ChoiceList import ChoiceList, ChoiceEntryComponent
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock
from Components.Console import Console
from Components.Harddisk import harddiskmanager, getProcMounts
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.Console import Console as ScreenConsole
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop
from Screens.TaskView import JobView
from Tools.BoundFunction import boundFunction
from Tools.Directories import pathExists, fileHas, fileExists
from Tools.HardwareInfo import HardwareInfo
from Tools.Multiboot import GetImagelist, GetCurrentImage
from Tools.Notifications import AddPopupWithCallback
from Tools.HardwareInfo import HardwareInfo

RAMCHEKFAILEDID = 'RamCheckFailedNotification'

hddchoises = []
for p in harddiskmanager.getMountedPartitions():
	if path.exists(p.mountpoint):
		d = path.normpath(p.mountpoint)
		if p.mountpoint != '/':
			hddchoises.append((p.mountpoint, d))
config.imagemanager = ConfigSubsection()
defaultprefix = getImageDistro() + '-' + getBoxType()
config.imagemanager.folderprefix = ConfigText(default=defaultprefix, fixed_size=False)
config.imagemanager.backuplocation = ConfigSelection(choices=hddchoises)
config.imagemanager.schedule = ConfigYesNo(default=False)
config.imagemanager.scheduletime = ConfigClock(default=0)  # 1:00
config.imagemanager.repeattype = ConfigSelection(default="daily", choices=[("daily", _("Daily")), ("weekly", _("Weekly")), ("monthly", _("30 Days"))])
config.imagemanager.backupretry = ConfigNumber(default=30)
config.imagemanager.backupretrycount = NoSave(ConfigNumber(default=0))
config.imagemanager.nextscheduletime = NoSave(ConfigNumber(default=0))
config.imagemanager.restoreimage = NoSave(ConfigText(default=getBoxType(), fixed_size=False))
config.imagemanager.autosettingsbackup = ConfigYesNo(default = True)
config.imagemanager.query = ConfigYesNo(default=True)
config.imagemanager.lastbackup = ConfigNumber(default=0)
config.imagemanager.number_to_keep = ConfigNumber(default=0)
config.imagemanager.imagefeed_twol = ConfigText(default="http://192.168.0.171/openvix-builds/", fixed_size=False)
config.imagemanager.imagefeed_ViX = ConfigText(default="http://www.openvix.co.uk/openvix-builds/", fixed_size=False)
config.imagemanager.imagefeed_ATV = ConfigText(default="http://images.mynonpublic.com/openatv/6.2/", fixed_size=False)
config.imagemanager.imagefeed_Pli = ConfigText(default="https://openpli.org/download/", fixed_size=False)

autoImageManagerTimer = None

if path.exists(config.imagemanager.backuplocation.value + 'imagebackups/imagerestore'):
	try:
		rmtree(config.imagemanager.backuplocation.value + 'imagebackups/imagerestore')
	except:
		pass

def ImageManagerautostart(reason, session=None, **kwargs):
	"""called with reason=1 to during /sbin/shutdown.sysvinit, with reason=0 at startup?"""
	global autoImageManagerTimer
	global _session
	now = int(time())
	if reason == 0:
		print "[ImageManager] AutoStart Enabled"
		if session is not None:
			_session = session
			if autoImageManagerTimer is None:
				autoImageManagerTimer = AutoImageManagerTimer(session)
	else:
		if autoImageManagerTimer is not None:
			print "[ImageManager] Stop"
			autoImageManagerTimer.stop()

class VIXImageManager(Screen):
	skin = """<screen name="VIXImageManager" position="center,center" size="560,400">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<ePixmap pixmap="skin_default/buttons/key_menu.png" position="0,40" size="35,25" alphatest="blend" transparent="1" zPosition="3"/>
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand"/>
		<widget name="backupstatus" position="10,370" size="400,30" font="Regular;20" zPosition="5"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle = _("Image manager")
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

		self['lab1'] = Label()
		self["backupstatus"] = Label()
		self["key_red"] = Button(_("Delete"))
		self["key_green"] = Button("New backup")
		self["key_yellow"] = Button(_("Downloads"))
		self["key_blue"] = Button(_("Flash"))

		self.BackupRunning = False
		if SystemInfo["canMultiBoot"]:
			self.mtdboot = "%s1" % SystemInfo["canMultiBoot"][2]
	 		if SystemInfo["canMultiBoot"][2] == "sda":
				self.mtdboot = "%s3" %getMachineMtdRoot()[0:8]
		self.imagelist = {}
		self.getImageList = None
		self.onChangedEntry = []
		self.oldlist = None
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.backupRunning)
		self.activityTimer.start(10)
		self.Console = Console()

		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next backup: ")
		self["backupstatus"].setText(str(backuptext))
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary

		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		desc = self["backupstatus"].text
		if item:
			name = item
		else:
			name = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def backupRunning(self):
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image manager")):
				self.BackupRunning = True
		if self.BackupRunning:
			self["key_green"].setText(_("View progress"))
		else:
			self["key_green"].setText(_("New backup"))
		self.activityTimer.startLongTimer(5)
		self.populate_List()

	def refreshUp(self):
		self["list"].instance.moveSelection(self["list"].instance.moveUp)

	def refreshDown(self):
		self["list"].instance.moveSelection(self["list"].instance.moveDown)

	def refreshList(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		mtimes = []
		for fil in images:
			if fil.endswith('.zip') or path.isdir(path.join(self.BackupDirectory, fil)):
				mtimes.append((fil, stat(self.BackupDirectory + fil).st_mtime)) # (filname, mtime)
		for fil in [x[0] for x in sorted(mtimes, key=lambda x: x[1], reverse=True)]: # sort by mtime
			self.emlist.append(fil)
		self["list"].setList(self.emlist)
		self["list"].show()

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100 * job.progress / float(job.end)))

	def showJobView(self, job):
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, backgroundable=False, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def populate_List(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if path.exists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				if p.mountpoint != '/':
					imparts.append((p.mountpoint, d))
		config.imagemanager.backuplocation.setChoices(imparts)

		if config.imagemanager.backuplocation.value.endswith('/'):
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value[:-1]
		else:
			mount = config.imagemanager.backuplocation.value + '/', config.imagemanager.backuplocation.value
		hdd = '/media/hdd/', '/media/hdd'
		if mount not in config.imagemanager.backuplocation.choices.choices and hdd not in config.imagemanager.backuplocation.choices.choices:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
											  {
											  'cancel': self.close,
											  "menu": self.createSetup,
											  }, -1)
			self['lab1'].setText(_("Device: None available") + "\n" + _("Select an image to flash:"))
		else:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "HelpActions"],
										  {
										  'cancel': self.close,
										  'red': self.keyDelete,
										  'green': self.GreenPressed,
										  'yellow': self.doDownLoad,
										  "menu": self.createSetup,
										  "up": self.refreshUp,
										  "down": self.refreshDown,
										  "displayHelp": self.doDownLoad,
										  }, -1)

			if SystemInfo["HasH9SD"]:
 				if fileHas("/proc/cmdline", "root=/dev/mmcblk0px") is True:		# dummy this for my system
					print "[ImageManager] HasH9Sd and mmc in boot" 
					self["key_blue"].setText("")
					self["key_blue"].show()
					pass
				else:
					print "[ImageManager] HasH9Sd and not MMC in boot" 
					self['restoreaction'] = ActionMap(['ColorActions', 'OkCancelActions'],
												  {
												  "ok": self.keyRestore,
												  'blue': self.keyRestore,
												  }, -1)
			else:
				print "[ImageManager] Not HasH9Sd" 
				self['restoreaction'] = ActionMap(['ColorActions', 'OkCancelActions'],
										  {
										  "ok": self.keyRestore,
										  'blue': self.keyRestore,
										  }, -1)
			self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
			s = statvfs(config.imagemanager.backuplocation.value)
			free = (s.f_bsize * s.f_bavail) / (1024 * 1024)
			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + ' ' + _('Free space:') + ' ' + str(free) + _('MB') + "\n" + _("Select an image to flash:"))

			try:
				if not path.exists(self.BackupDirectory):
					mkdir(self.BackupDirectory, 0755)
				if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-swapfile_backup'):
					system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-swapfile_backup')
					remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-swapfile_backup')
				self.refreshList()
			except:
				self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + "\n" + _("There is a problem with this device. Please reformat it and try again."))

	def createSetup(self):
		self.session.openWithCallback(self.setupDone, Setup, 'viximagemanager', 'SystemPlugins/ViX', self.menu_path, PluginLanguageDomain)

	def doDownLoad(self):
		self.urli = 'http://192.168.0.171/openvix-builds/'
		choices = [("OpenTwol", 1), ("OpenViX", 2), ("OpenATV", 3), ("OpenPli", 4)]
		self.message = _("Do you want to change download url")
		self.session.openWithCallback(self.doDownload2, MessageBox, self.message, list=choices, default=1, simple=True)

	def doDownload2(self, retval):
		if retval:
			print "[ImageManager][retval] %s is retval" % retval
			retvalx = int(retval) 
			urlchoices = [config.imagemanager.imagefeed_twol.value, config.imagemanager.imagefeed_twol.value, config.imagemanager.imagefeed_ViX.value, config.imagemanager.imagefeed_ATV.value, config.imagemanager.imagefeed_Pli.value]
			self.urli = urlchoices[retvalx]
			self.session.openWithCallback(self.refreshList, ImageManagerDownload, self.menu_path, self.BackupDirectory, self.urli)

	def setupDone(self, test=None):
		if config.imagemanager.folderprefix.value == '':
			config.imagemanager.folderprefix.value = defaultprefix
			config.imagemanager.folderprefix.save()
		self.populate_List()
		self.doneConfiguring()

	def doneConfiguring(self):
		now = int(time())
		if config.imagemanager.schedule.value:
			if autoImageManagerTimer is not None:
				print "[ImageManager] Backup Schedule Enabled at", strftime("%c", localtime(now))
				autoImageManagerTimer.backupupdate()
		else:
			if autoImageManagerTimer is not None:
				global BackupTime
				BackupTime = 0
				print "[ImageManager] Backup Schedule Disabled at", strftime("%c", localtime(now))
				autoImageManagerTimer.backupstop()
		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next backup: ")
		self["backupstatus"].setText(str(backuptext))

	def keyDelete(self):
		self.sel = self['list'].getCurrent()
		self["list"].instance.moveSelectionTo(0)
		if self.sel.endswith('.zip'):
			remove(self.BackupDirectory + self.sel)
		else:
			rmtree(self.BackupDirectory + self.sel)
		self.populate_List()

	def GreenPressed(self):
		backup = None
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image manager")):
				backup = job
				self.BackupRunning = True
		if self.BackupRunning and backup:
			self.showJobView(backup)
		else:
			self.keyBackup()

	def keyBackup(self):
		message = _("Do you want to create a full image backup?\nThis can take about 6 minutes to complete.")
		ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Backup confirmation"))

	def doBackup(self, answer):
		if answer is True:
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			self.BackupRunning = True
			self["key_green"].setText(_("View progress"))
			self["key_green"].show()
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Image manager")):
					break
			self.showJobView(job)

	def doSettingsBackup(self):
		from Plugins.SystemPlugins.ViX.BackupManager import BackupFiles
		self.BackupFiles = BackupFiles(self.session, False, True)
		Components.Task.job_manager.AddJob(self.BackupFiles.createBackupJob())
		Components.Task.job_manager.in_background = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_('Backup manager')):
				break
		self.session.openWithCallback(self.keyRestore3, JobView, job,  cancelable = False, backgroundable = False, afterEventChangeable = False, afterEvent="close")


#		#default layout for 				Mut@nt HD51/Osmio4k x = 0,1						 Giga4K						SF8008
# boot								/dev/mmcblk0p1						/dev/mmcblk0p1				/dev/mmcblk0p3
# STARTUP_1 			Image 1: boot emmcflash0.kernel1 'root=/dev/mmcblkxp3 rw rootwait'	boot emmcflash0.kernel1: 'root=/dev/mmcblk0p5		boot emmcflash0.kernel 'root=/dev/mmcblk0p13 
# STARTUP_2 			Image 2: boot emmcflash0.kernel2 'root=/dev/mmcblkxp5 rw rootwait'      boot emmcflash0.kernel2: 'root=/dev/mmcblk0p7		boot usb0.sda1 'root=/dev/sda2
# STARTUP_3		        Image 3: boot emmcflash0.kernel3 'root=/dev/mmcblkxp7 rw rootwait'	boot emmcflash0.kernel3: 'root=/dev/mmcblk0p9		boot usb0.sda3 'root=/dev/sda4
# STARTUP_4		        Image 4: boot emmcflash0.kernel4 'root=/dev/mmcblkxp9 rw rootwait'	NOT IN USE due to Rescue mode in mmcblk0p3

	def keyRestore(self):
		self.sel = self['list'].getCurrent()
		if not self.sel:
			return
		self.HasSDmmc = False
		self.multibootslot = 1
		self.MTDKERNEL = getMachineMtdKernel()
		self.MTDROOTFS = getMachineMtdRoot()	
		if getMachineMake() == 'et8500' and path.exists('/proc/mtd'):
			self.dualboot = self.dualBoot()
		recordings = self.session.nav.getRecordings()
		if not recordings:
			next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
		if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 360):
			self.message = _("Recording(s) are in progress or coming up in few seconds!\nDo you still want to flash image\n%s?") % self.sel
		else:
			self.message = _("Do you want to flash image\n%s") % self.sel
		if SystemInfo["canMultiBoot"]:
			if SystemInfo["HasSDmmc"]:
 				if pathExists('/dev/%s4' %SystemInfo["canMultiBoot"][2]):
					self.HasSDmmc = True
					self.getImageList = GetImagelist(self.keyRestore1)
				elif config.imagemanager.autosettingsbackup.value:
					self.doSettingsBackup()
				else:
					self.keyRestore3()
			else:
				self.getImageList = GetImagelist(self.keyRestore1)
		elif config.imagemanager.autosettingsbackup.value:
			self.doSettingsBackup()
		else:
			self.keyRestore3()


	def keyRestore1(self, imagedict):
		self.imagelist = imagedict
		self.getImageList = None
		choices = []
		HIslot = len(imagedict) + 1
		currentimageslot = GetCurrentImage()
		if SystemInfo["HasSDmmc"]:
			currentimageslot += 1
		print "ImageManager", currentimageslot, self.imagelist
		for x in range(1,HIslot):
			choices.append(((_("slot%s - %s (current image)") if x == currentimageslot else _("slot%s - %s")) % (x, imagedict[x]['imagename']), (x)))
		self.session.openWithCallback(self.keyRestore2, MessageBox, self.message, list=choices, default=currentimageslot, simple=True)

	def keyRestore2(self, retval):
		if retval:
			if SystemInfo["canMultiBoot"]:
				self.multibootslot = retval
				print "ImageManager", retval, self.imagelist
				if SystemInfo["HasSDmmc"]:
					if "sd" in self.imagelist[retval]['part']:
						self.MTDKERNEL = "%s%s" %(SystemInfo["canMultiBoot"][2], int(self.imagelist[retval]['part'][3])-1)
						self.MTDROOTFS = "%s" %(self.imagelist[retval]['part'])
					else:
						self.MTDKERNEL = getMachineMtdKernel()
						self.MTDROOTFS = getMachineMtdRoot()					
			if self.sel:
				if config.imagemanager.autosettingsbackup.value:
					self.doSettingsBackup()
				else:
					self.keyRestore3()
			else:
				self.session.open(MessageBox, _("There is no image to flash."), MessageBox.TYPE_INFO, timeout=10)
		else:
			self.session.open(MessageBox, _("You have decided not to flash image."), MessageBox.TYPE_INFO, timeout=10)


	def keyRestore3(self, val = None):
		self.restore_infobox = self.session.open(MessageBox, _("Please wait while the flash prepares."), MessageBox.TYPE_INFO, timeout=180, enable_input=False)
		self.TEMPDESTROOT = self.BackupDirectory + 'imagerestore'
		if self.sel.endswith('.zip'):
			if not path.exists(self.TEMPDESTROOT):
				mkdir(self.TEMPDESTROOT, 0755)
			self.Console.ePopen('unzip -o %s%s -d %s' % (self.BackupDirectory, self.sel, self.TEMPDESTROOT), self.keyRestore4)
		else:
			self.TEMPDESTROOT = self.BackupDirectory + self.sel
			self.keyRestore4(0, 0)

	def keyRestore4(self, result, retval, extra_args=None):
		if retval == 0:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("Flash image unzip successful."), MessageBox.TYPE_INFO, timeout=4)
			if getMachineMake() == 'et8500' and self.dualboot:
				message = _("ET8500 Multiboot: Yes to restore OS1 No to restore OS2:\n ") + self.sel
				ybox = self.session.openWithCallback(self.keyRestore5_ET8500, MessageBox, message, MessageBox.TYPE_YESNO)
				ybox.setTitle(_("ET8500 Image Restore"))
			else:
				MAINDEST = '%s/%s' % (self.TEMPDESTROOT,getImageFolder())
				if pathExists("%s/SDAbackup" %MAINDEST) and self.multibootslot !=1:
						self.session.open(MessageBox, _("Multiboot only able to restore this backup to mmc slot1"), MessageBox.TYPE_INFO, timeout=20)
						print "[ImageManager] SF8008 mmc restore to SDcard failed:\n",
						self.close()
				else:
					self.keyRestore6(0)
		else:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("Unzip error (also sent to any debug log):\n%s") % result, MessageBox.TYPE_INFO, timeout=20)
			print "[ImageManager] unzip failed:\n", result
			self.close()

	def keyRestore5_ET8500(self, answer):
		if answer:
			self.keyRestore6(0)
		else:
			self.keyRestore6(1)

	def keyRestore6(self,ret):
		MAINDEST = '%s/%s' % (self.TEMPDESTROOT,getImageFolder())
		CMD = " "
		if ret == 0:
			if SystemInfo["canMultiBoot"]:
 				if SystemInfo["HasSDmmc"]:
					CMD = "/usr/bin/ofgwrite -r%s -k%s '%s'" % (self.MTDROOTFS, self.MTDKERNEL, MAINDEST)
				else:
					CMD = "/usr/bin/ofgwrite -r -k -m%s '%s'" % (self.multibootslot, MAINDEST)
 			elif SystemInfo["HasHiSi"]:
				CMD = "/usr/bin/ofgwrite -r%s -k%s '%s'" % (self.MTDROOTFS, self.MTDKERNEL, MAINDEST)
			elif SystemInfo["HasH9SD"] and fileHas("/proc/cmdline", "root=/dev/mmcblk0p1") is True: 
				if fileExists("%s/rootfs.tar.bz2" %MAINDEST):
					CMD = "/usr/bin/ofgwrite -rmmcblk0p1 '%s'" % MAINDEST
				else:
					self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("Zgemma H9 unable to restore H9 ubi root to SDcard"), MessageBox.TYPE_INFO, timeout=20)
			else:
				CMD = "/usr/bin/ofgwrite -r -k '%s'" % MAINDEST
		else:
			CMD = '/usr/bin/ofgwrite -rmtd4 -kmtd3  %s/' % (MAINDEST)
		config.imagemanager.restoreimage.setValue(self.sel)
		if CMD == " ":
			self.close()
		else:
			print '[ImageManager] running commnd:',CMD
			self.Console.ePopen(CMD, self.ofgwriteResult)
			fbClass.getInstance().lock()

	def ofgwriteResult(self, result, retval, extra_args=None):
		fbClass.getInstance().unlock()
		if retval == 0:
			if SystemInfo["canMultiBoot"]:
				if SystemInfo["HasSDmmc"] and self.HasSDmmc is False:
					self.session.open(TryQuitMainloop, 2)
				print "[ImageManager] slot %s result %s\n" %(self.multibootslot, result)
				self.container = Console()
				if pathExists('/tmp/startupmount'):
					self.ContainterFallback()
				else:
					mkdir('/tmp/startupmount')
					self.container.ePopen('mount /dev/%s /tmp/startupmount' % self.mtdboot, self.ContainterFallback)
			else:
				self.session.open(TryQuitMainloop, 2)
		else:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("OFGwrite error (also sent to any debug log):\n%s") % result, MessageBox.TYPE_INFO, timeout=20)
			print "[ImageManager] OFGWriteResult failed:\n", result

	def ContainterFallback(self, data=None, retval=None, extra_args=None):
		self.container.killAll()
		if pathExists("/tmp/startupmount/STARTUP"):
			copyfile("/tmp/startupmount/STARTUP_%s" % self.multibootslot, "/tmp/startupmount/STARTUP")
			self.session.open(TryQuitMainloop, 2)
		else:
			self.session.open(MessageBox, _("Multiboot ERROR! - no STARTUP in boot partition."), MessageBox.TYPE_INFO, timeout=20)

	def dualBoot(self):
		rootfs2 = False
		kernel2 = False
		f = open("/proc/mtd")
		L = f.readlines()
		for x in L:
			if 'rootfs2' in x:
				rootfs2 = True
			if 'kernel2' in x:
				kernel2 = True
		f.close()
		if rootfs2 and kernel2:
			return True
		else:
			return False

class AutoImageManagerTimer:
	def __init__(self, session):
		self.session = session
		self.backuptimer = eTimer()
		self.backuptimer.callback.append(self.BackuponTimer)
		self.backupactivityTimer = eTimer()
		self.backupactivityTimer.timeout.get().append(self.backupupdatedelay)
		now = int(time())
		global BackupTime
		if config.imagemanager.schedule.value:
			print "[ImageManager] Backup Schedule Enabled at ", strftime("%c", localtime(now))
			if now > 1262304000:
				self.backupupdate()
			else:
				print "[ImageManager] Backup Time not yet set."
				BackupTime = 0
				self.backupactivityTimer.start(36000)
		else:
			BackupTime = 0
			print "[ImageManager] Backup Schedule Disabled at", strftime("(now=%c)", localtime(now))
			self.backupactivityTimer.stop()

	def backupupdatedelay(self):
		self.backupactivityTimer.stop()
		self.backupupdate()

	def getBackupTime(self):
		backupclock = config.imagemanager.scheduletime.value
		#
		# Work out the time of the *NEXT* backup - which is the configured clock
		# time on the nth relevant day after the last recorded backup day.
		# The last backup time will have been set as 12:00 on the day it
		# happened. All we use is the actual day from that value.
		#
		lastbkup_t = int(config.imagemanager.lastbackup.value)
		if config.imagemanager.repeattype.value == "daily":
			nextbkup_t = lastbkup_t + 24*3600
		elif config.imagemanager.repeattype.value == "weekly":
			nextbkup_t = lastbkup_t + 7*24*3600
		elif config.imagemanager.repeattype.value == "monthly":
			nextbkup_t = lastbkup_t + 30*24*3600
		nextbkup = localtime(nextbkup_t)
		return int(mktime((nextbkup.tm_year, nextbkup.tm_mon, nextbkup.tm_mday, backupclock[0], backupclock[1], 0, nextbkup.tm_wday, nextbkup.tm_yday, nextbkup.tm_isdst)))

	def backupupdate(self, atLeast=0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				self.backuptimer.startLongTimer(60) # Backup missed - run it 60s from now
				print "[ImageManager] Backup Time overdue - running in 60s"
			else:
				delay = BackupTime - now # Backup in future - set the timer...
				self.backuptimer.startLongTimer(delay)
		else:
			BackupTime = -1
		print "[ImageManager] Backup Time set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
		return BackupTime

	def backupstop(self):
		self.backuptimer.stop()

	def BackuponTimer(self):
		self.backuptimer.stop()
		now = int(time())
		wake = self.getBackupTime()
		# If we're close enough, we're okay...
		atLeast = 0
		if wake - now < 60:
			print "[ImageManager] Backup onTimer occured at", strftime("%c", localtime(now))
			from Screens.Standby import inStandby

			if not inStandby and config.imagemanager.query.value:
				message = _("Your %s %s is about to create a full image backup, this can take about 6 minutes to complete.\nDo you want to allow this?") % (getMachineBrand(), getMachineName())
				ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout=30)
				ybox.setTitle('Scheduled backup.')
			else:
				print "[ImageManager] in Standby or no querying, so just running backup", strftime("%c", localtime(now))
				self.doBackup(True)
		else:
			print '[ImageManager] We are not close enough', strftime("%c", localtime(now))
			self.backupupdate(60)

	def doBackup(self, answer):
		now = int(time())
		if answer is False:
			if config.imagemanager.backupretrycount.value < 2:
				print '[ImageManager] Number of retries', config.imagemanager.backupretrycount.value
				print "[ImageManager] Backup delayed."
				repeat = config.imagemanager.backupretrycount.value
				repeat += 1
				config.imagemanager.backupretrycount.setValue(repeat)
				BackupTime = now + (int(config.imagemanager.backupretry.value) * 60)
				print "[ImageManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
				self.backuptimer.startLongTimer(int(config.imagemanager.backupretry.value) * 60)
			else:
				atLeast = 60
				print "[ImageManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout=10)
				config.imagemanager.backupretrycount.setValue(0)
				self.backupupdate(atLeast)
		else:
			print "[ImageManager] Running Backup", strftime("%c", localtime(now))
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			#      Note that fact that the job has been *scheduled*.
			#      We do *not* just note successful completion, as that would
			#      result in a loop on issues such as disk-full.
			#      Also all that we actually want to know is the day, not the time, so
			#      we actually remember midday, which avoids problems around DLST changes
			#      for backups scheduled within an hour of midnight.
			#
			sched = localtime(time())
			sched_t = int(mktime((sched.tm_year, sched.tm_mon, sched.tm_mday, 12, 0, 0, sched.tm_wday, sched.tm_yday, sched.tm_isdst)))
			config.imagemanager.lastbackup.value = sched_t
			config.imagemanager.lastbackup.save()
		#self.close()

class ImageBackup(Screen):
	skin = """
	<screen name="VIXImageManager" position="center,center" size="560,400">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session, updatebackup=False):
		Screen.__init__(self, session)
		self.Console = Console()
		self.BackupDevice = config.imagemanager.backuplocation.value
		print "[ImageManager] Device: " + self.BackupDevice
		self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
		print "[ImageManager] Directory: " + self.BackupDirectory
		self.BackupDate = strftime('%Y%m%d_%H%M%S', localtime())
		self.WORKDIR = self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-temp'
		self.TMPDIR = self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + '-mount'
		backupType = "-"
		if updatebackup:
			backupType = "-SoftwareUpdate-"
		imageSubBuild = ""
		if getImageType() != 'release':
			imageSubBuild = ".%s" % getImageDevBuild()
		self.MAINDESTROOT = self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + backupType + getImageVersion() + '.' + getImageBuild() + imageSubBuild + '-' + self.BackupDate
		self.KERNELFILE = getMachineKernelFile()
		self.ROOTFSFILE = getMachineRootFile()
		self.MAINDEST = self.MAINDESTROOT + '/' + getImageFolder() + '/'
		self.MAINDEST2 = self.MAINDESTROOT + '/'
		self.MODEL = getBoxType()
		self.MCBUILD = getMachineBuild()
		self.KERN = "mmc"
		if SystemInfo["canMultiBoot"]:
			kernel = GetCurrentImage()
			if SystemInfo["HasSDmmc"]:
				f = open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read()
				if "sda" in f :
					self.KERN = "sda"
					kern =  kernel*2
					self.MTDKERNEL = "sda%s" %(kern-1)
					self.MTDROOTFS = "sda%s" %(kern)
				else:
					self.MTDKERNEL = getMachineMtdKernel()
					self.MTDROOTFS = getMachineMtdRoot()
			else:					
				self.addin = SystemInfo["canMultiBoot"][0]
				self.MTDBOOT = "%s1" %SystemInfo["canMultiBoot"][2]
				self.MTDKERNEL = "%s%s" %(SystemInfo["canMultiBoot"][2], kernel*2 +self.addin -1)
				self.MTDROOTFS = "%s%s" %(SystemInfo["canMultiBoot"][2], kernel*2 +self.addin)
				print '[ImageManager] MTD Boot:',self.MTDBOOT
		else:
			self.MTDKERNEL = getMachineMtdKernel()
			self.MTDROOTFS = getMachineMtdRoot()
		if getMachineBuild() in ("gb7252"):
			self.GB4Kbin = 'boot.bin'
			self.GB4Krescue = 'rescue.bin'
		print '[ImageManager] Model:',self.MODEL
		print '[ImageManager] Machine Build:',self.MCBUILD
		print '[ImageManager] Kernel File:',self.KERNELFILE
		print '[ImageManager] Root File:',self.ROOTFSFILE
		print '[ImageManager] MTD Kernel:',self.MTDKERNEL
		print '[ImageManager] MTD Root:',self.MTDROOTFS
		print '[ImageManager] Type:',getImageFileSystem()
		print '[ImageManager] MAINDEST:',self.MAINDEST
		print '[ImageManager] WORKDIR:',self.WORKDIR
		print '[ImageManager] TMPDIR:',self.TMPDIR
		if 'ubi' in getImageFileSystem():
			self.ROOTDEVTYPE = 'ubifs'
			self.ROOTFSTYPE = 'ubifs'
			self.KERNELFSTYPE = 'gz'
		elif getImageFileSystem().replace(' ','') == 'tar.bz2':
			self.ROOTDEVTYPE = 'tar.bz2'
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
		elif getImageFileSystem() in ('octagonemmc', 'gigablueemmc'):		# SF8008, GB trio 4K
			self.ROOTDEVTYPE = 'tar.bz2'
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
			self.MTDBOOT = "none"
			self.EMMCIMG = "usb_update.bin"
		elif 'dinobotemmc' in getImageFileSystem():
			self.ROOTDEVTYPE = 'tar.bz2'
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
		elif 'hdfastboot8gb' in getImageFileSystem():				# H9combo, HD60, HD61 receiver with multiple eMMC partitions in class
			self.ROOTDEVTYPE = 'tar.bz2'
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
			self.MTDBOOT = "none"
			self.EMMCIMG = "rootfs.fastboot.gz"
		elif getImageFileSystem().replace(' ','') in ('hdemmc', 'hd-emmc', 'airdigitalemmc'):	# handle new & old formats
			self.ROOTDEVTYPE = 'hdemmc'					# HD51/H7 receiver with multiple eMMC partitions in class
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
			self.EMMCIMG = "disk.img"
		elif 'emmcimg' in getImageFileSystem():	
			self.ROOTDEVTYPE = 'emmcimg'					# osmio4k receiver with multiple eMMC partitions in class
			self.ROOTFSTYPE = 'tar.bz2'
			self.KERNELFSTYPE = 'bin'
			self.EMMCIMG = "emmc.img"
		else:
			self.ROOTDEVTYPE = 'jffs2'
			self.ROOTFSTYPE= 'jffs2'
			self.KERNELFSTYPE = 'gz'
		print '[ImageManager] ROOTDEVTYPE:',self.ROOTDEVTYPE
		print '[ImageManager] ROOTFSTYPE:',self.ROOTFSTYPE
		print '[ImageManager] KERNELFSTYPE:',self.KERNELFSTYPE
		self.swapdevice = ""
		self.RamChecked = False
		self.SwapCreated = False
		self.Stage1Completed = False
		self.Stage2Completed = False
		self.Stage3Completed = False
		self.Stage4Completed = False
		self.Stage5Completed = False
		self.Stage6Completed = False

	def createBackupJob(self):
		job = Components.Task.Job(_("Image manager"))

		task = Components.Task.PythonTask(job, _("Setting up..."))
		task.work = self.JobStart
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Checking free RAM.."), timeoutCount=10)
		task.check = lambda: self.RamChecked
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating SWAP.."), timeoutCount=120)
		task.check = lambda: self.SwapCreated
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backing up kernel..."))
		task.work = self.doBackup1
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up kernel..."), timeoutCount=900)
		task.check = lambda: self.Stage1Completed
		task.weighting = 35

		task = Components.Task.PythonTask(job, _("Backing up root file system..."))
		task.work = self.doBackup2
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up root file system..."), timeoutCount=900)
		task.check = lambda: self.Stage2Completed
		task.weighting = 15

		task = Components.Task.PythonTask(job, _("Backing up eMMC partitions for USB flash ..."))
		task.work = self.doBackup3
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up eMMC partitions for USB flash..."), timeoutCount=900)
		task.check = lambda: self.Stage3Completed
		task.weighting = 15
	
		task = Components.Task.PythonTask(job, _("Removing temp mounts..."))
		task.work = self.doBackup4
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Removing temp mounts..."), timeoutCount=30)
		task.check = lambda: self.Stage4Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Moving to backup Location..."))
		task.work = self.doBackup5
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Moving to backup Location..."), timeoutCount=30)
		task.check = lambda: self.Stage5Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Creating zip..."))
		task.work = self.doBackup6
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating zip..."), timeoutCount=900)
		task.check = lambda: self.Stage6Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backup complete."))
		task.work = self.BackupComplete
		task.weighting = 5

		return job

	def JobStart(self):
		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup"):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
		except Exception, e:
			print str(e)
			print "[ImageManager] Device: " + config.imagemanager.backuplocation.value + ", i don't seem to have write access to this device."

		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail) / (1024 * 1024)
		if int(free) < 200:
			AddPopupWithCallback(self.BackupComplete,
								 _("The backup location does not have enough free space." + "\n" + self.BackupDevice + "only has " + str(free) + "MB free."),
								 MessageBox.TYPE_INFO,
								 10,
								 'RamCheckFailedNotification'
			)
		else:
			self.MemCheck()

	def MemCheck(self):
		memfree = 0
		swapfree = 0
		f = open('/proc/meminfo', 'r')
		for line in f.readlines():
			if line.find('MemFree') != -1:
				parts = line.strip().split()
				memfree = int(parts[1])
			elif line.find('SwapFree') != -1:
				parts = line.strip().split()
				swapfree = int(parts[1])
		f.close()
		TotalFree = memfree + swapfree
		print '[ImageManager] Stage1: Free Mem', TotalFree
		if int(TotalFree) < 3000:
			supported_filesystems = frozenset(('ext4', 'ext3', 'ext2'))
			candidates = []
			mounts = getProcMounts()
			for partition in harddiskmanager.getMountedPartitions(False, mounts):
				if partition.filesystem(mounts) in supported_filesystems:
					candidates.append((partition.description, partition.mountpoint))
			for swapdevice in candidates:
				self.swapdevice = swapdevice[1]
			if self.swapdevice:
				print '[ImageManager] Stage1: Creating SWAP file.'
				self.RamChecked = True
				self.MemCheck2()
			else:
				print '[ImageManager] Sorry, not enough free RAM found, and no physical devices that supports SWAP attached'
				AddPopupWithCallback(self.BackupComplete,
									 _("Sorry, not enough free RAM found, and no physical devices that supports SWAP attached. Can't create SWAP file on network or fat32 file-systems, unable to make backup."),
									 MessageBox.TYPE_INFO,
									 10,
									 'RamCheckFailedNotification'
				)
		else:
			print '[ImageManager] Stage1: Found Enough RAM'
			self.RamChecked = True
			self.SwapCreated = True

	def MemCheck2(self):
		self.Console.ePopen("dd if=/dev/zero of=" + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup bs=1024 count=61440", self.MemCheck3)

	def MemCheck3(self, result, retval, extra_args=None):
		if retval == 0:
			self.Console.ePopen("mkswap " + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup", self.MemCheck4)

	def MemCheck4(self, result, retval, extra_args=None):
		if retval == 0:
			self.Console.ePopen("swapon " + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup", self.MemCheck5)

	def MemCheck5(self, result, retval, extra_args=None):
		self.SwapCreated = True

	def doBackup1(self):
		print '[ImageManager] Stage1: Creating tmp folders.', self.BackupDirectory
		print '[ImageManager] Stage1: Creating backup Folders.'
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		mkdir(self.WORKDIR, 0644)
		if path.exists(self.TMPDIR + '/root') and path.ismount(self.TMPDIR + '/root'):
			system('umount ' + self.TMPDIR + '/root')
		elif path.exists(self.TMPDIR + '/root'):
			rmtree(self.TMPDIR + '/root')
		if path.exists(self.TMPDIR):
			rmtree(self.TMPDIR)
		makedirs(self.TMPDIR, 0644)
		makedirs(self.TMPDIR + '/root', 0644)
		makedirs(self.MAINDESTROOT, 0644)
		self.commands = []
		makedirs(self.MAINDEST, 0644)
		print '[ImageManager] Stage1: Making Kernel Image.'
		if self.KERNELFSTYPE == 'bin':
			self.command = 'dd if=/dev/%s of=%s/vmlinux.bin' % (self.MTDKERNEL ,self.WORKDIR)
		else:
			self.command = 'nanddump /dev/%s -f %s/vmlinux.gz' % (self.MTDKERNEL ,self.WORKDIR)
		self.Console.ePopen(self.command, self.Stage1Complete)

	def Stage1Complete(self, result, retval, extra_args=None):
		if retval == 0:
			self.Stage1Completed = True
			print '[ImageManager] Stage1: Complete.'

	def doBackup2(self):
		print '[ImageManager] Stage2: Making Root Image.'
		if self.ROOTDEVTYPE == 'jffs2':
			print '[ImageManager] Stage2: JFFS2 Detected.'
			if getMachineBuild() == 'gb800solo':
				JFFS2OPTIONS = " --disable-compressor=lzo -e131072 -l -p125829120"
			else:
				JFFS2OPTIONS = " --disable-compressor=lzo --eraseblock=0x20000 -n -l"
			self.commands.append('mount --bind / %s/root' % self.TMPDIR)
			self.commands.append('mkfs.jffs2 --root=%s/root --faketime --output=%s/rootfs.jffs2 %s' % (self.TMPDIR, self.WORKDIR, JFFS2OPTIONS))
		elif self.ROOTFSTYPE == 'tar.bz2':
			print '[ImageManager] Stage2: TAR.BZIP Detected.'
			if SystemInfo["canMultiBoot"]:
				self.commands.append('mount /dev/%s %s/root' %(self.MTDROOTFS, self.TMPDIR))
			else:
				self.commands.append('mount --bind / %s/root' % self.TMPDIR)
			self.commands.append("/bin/tar -cf %s/rootfs.tar -C %s/root --exclude=/var/nmbd/* ." % (self.WORKDIR, self.TMPDIR))
			self.commands.append("/usr/bin/bzip2 %s/rootfs.tar" % self.WORKDIR)
			if getMachineBuild() in ("gb7252"):
				self.commands.append("dd if=/dev/mmcblk0p1 of=%s/boot.bin" % self.WORKDIR)
				self.commands.append("dd if=/dev/mmcblk0p3 of=%s/rescue.bin" % self.WORKDIR)
				print '[ImageManager] Stage2: Create: boot dump boot.bin:',self.MODEL
				print '[ImageManager] Stage2: Create: rescue dump rescue.bin:',self.MODEL
		else:
			print '[ImageManager] Stage2: UBIFS Detected.'
			UBINIZE_ARGS = getMachineUBINIZE()
			MKUBIFS_ARGS = getMachineMKUBIFS()
			output = open('%s/ubinize.cfg' % self.WORKDIR, 'w')
			output.write('[ubifs]\n')
			output.write('mode=ubi\n')
			output.write('image=%s/root.ubi\n' % self.WORKDIR)
			output.write('vol_id=0\n')
			output.write('vol_type=dynamic\n')
			output.write('vol_name=rootfs\n')
			output.write('vol_flags=autoresize\n')
			output.close()
			self.commands.append('mount --bind / %s/root' % self.TMPDIR)
			if getMachineBuild() in ("h9"):
				z = open('/proc/cmdline', 'r').read()
				if SystemInfo["HasMMC"] and "root=/dev/mmcblk0p1" in z: 
					self.commands.append("/bin/tar -cf %s/rootfs.tar -C %s/root --exclude=/var/nmbd/* ." % (self.WORKDIR, self.TMPDIR))
					self.commands.append("/usr/bin/bzip2 %s/rootfs.tar" % self.WORKDIR)
				else:
					self.commands.append('touch %s/root.ubi' % self.WORKDIR)
					self.commands.append('mkfs.ubifs -r %s/root -o %s/root.ubi %s' % (self.TMPDIR, self.WORKDIR, MKUBIFS_ARGS))
					self.commands.append('ubinize -o %s/rootfs.ubifs %s %s/ubinize.cfg' % (self.WORKDIR, UBINIZE_ARGS, self.WORKDIR))
				self.commands.append('echo " "')
				self.commands.append('echo "' + _("Create:") + " fastboot dump" + '"')
				self.commands.append("dd if=/dev/mtd0 of=%s/fastboot.bin" % self.WORKDIR)
				self.commands.append("dd if=/dev/mtd0 of=%s/fastboot.bin" % self.MAINDEST2)
				self.commands.append('echo "' + _("Create:") + " bootargs dump" + '"')
				self.commands.append("dd if=/dev/mtd1 of=%s/bootargs.bin" % self.WORKDIR)
				self.commands.append("dd if=/dev/mtd1 of=%s/bootargs.bin" % self.MAINDEST2)
				self.commands.append('echo "' + _("Create:") + " baseparam dump" + '"')
				self.commands.append("dd if=/dev/mtd2 of=%s/baseparam.bin" % self.WORKDIR)
				self.commands.append('echo "' + _("Create:") + " pq_param dump" + '"')
				self.commands.append("dd if=/dev/mtd3 of=%s/pq_param.bin" % self.WORKDIR)
				self.commands.append('echo "' + _("Create:") + " logo dump" + '"')
				self.commands.append("dd if=/dev/mtd4 of=%s/logo.bin" % self.WORKDIR)
		self.Console.eBatch(self.commands, self.Stage2Complete, debug=False)

	def Stage2Complete(self, extra_args=None):
		if len(self.Console.appContainers) == 0:
			self.Stage2Completed = True
			print '[ImageManager] Stage2: Complete.'

	def doBackup3(self):
		print '[ImageManager] Stage3: Making eMMC Image.'
		self.commandMB = []
		if self.ROOTDEVTYPE == 'hdemmc':
			print '[ImageManager] hd51: EMMC Detected.'		# hd51 receiver with multiple eMMC partitions in class	
			BLOCK_SIZE=512
			BLOCK_SECTOR=2
			IMAGE_ROOTFS_ALIGNMENT=1024
			BOOT_PARTITION_SIZE=3072
			KERNEL_PARTITION_SIZE=8192
			ROOTFS_PARTITION_SIZE=819200
			EMMC_IMAGE_SIZE=3817472
			KERNEL_PARTITION_OFFSET = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			ROOTFS_PARTITION_OFFSET = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SECOND_KERNEL_PARTITION_OFFSET = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			SECOND_ROOTFS_PARTITION_OFFSET = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			THIRD_KERNEL_PARTITION_OFFSET = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			THIRD_ROOTFS_PARTITION_OFFSET = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			FOURTH_KERNEL_PARTITION_OFFSET = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			FOURTH_ROOTFS_PARTITION_OFFSET = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SWAP_PARTITION_OFFSET = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			EMMC_IMAGE = "%s/%s"% (self.WORKDIR,self.EMMCIMG)
			EMMC_IMAGE_SEEK = int(EMMC_IMAGE_SIZE) * int(BLOCK_SECTOR)
			self.commandMB.append('dd if=/dev/zero of=%s bs=%s count=0 seek=%s' % (EMMC_IMAGE, BLOCK_SIZE , EMMC_IMAGE_SEEK))
			self.commandMB.append('parted -s %s mklabel gpt' %EMMC_IMAGE)
			PARTED_END_BOOT = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart boot fat16 %s %s' % (EMMC_IMAGE, IMAGE_ROOTFS_ALIGNMENT, PARTED_END_BOOT ))
			PARTED_END_KERNEL1 = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel1 %s %s' % (EMMC_IMAGE, KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL1 ))
			PARTED_END_ROOTFS1 = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs1 ext4 %s %s' % (EMMC_IMAGE, ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS1 ))
			PARTED_END_KERNEL2 = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel2 %s %s' % (EMMC_IMAGE, SECOND_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL2 ))
			PARTED_END_ROOTFS2 = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs2 ext4 %s %s' % (EMMC_IMAGE, SECOND_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS2 ))
			PARTED_END_KERNEL3 = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel3 %s %s' % (EMMC_IMAGE, THIRD_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL3 ))
			PARTED_END_ROOTFS3 = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs3 ext4 %s %s' % (EMMC_IMAGE, THIRD_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS3 ))
			PARTED_END_KERNEL4 = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel4 %s %s' % (EMMC_IMAGE, FOURTH_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL4 ))
			PARTED_END_ROOTFS4 = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs4 ext4 %s %s' % (EMMC_IMAGE, FOURTH_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS4 ))
			self.commandMB.append('parted -s %s unit KiB mkpart swap linux-swap %s 100%%' % (EMMC_IMAGE, SWAP_PARTITION_OFFSET))

			BOOT_IMAGE_SEEK = int(IMAGE_ROOTFS_ALIGNMENT) * int(BLOCK_SECTOR)
			self.commandMB.append('dd if=/dev/%s of=%s seek=%s' % (self.MTDBOOT, EMMC_IMAGE, BOOT_IMAGE_SEEK ))
			KERNEL_IMAGE_SEEK = int(KERNEL_PARTITION_OFFSET) * int(BLOCK_SECTOR)
			self.commandMB.append('dd if=/dev/%s of=%s seek=%s' % (self.MTDKERNEL, EMMC_IMAGE, KERNEL_IMAGE_SEEK ))
			ROOTFS_IMAGE_SEEK = int(ROOTFS_PARTITION_OFFSET) * int(BLOCK_SECTOR)
			self.commandMB.append('dd if=/dev/%s of=%s seek=%s' % (self.MTDROOTFS, EMMC_IMAGE, ROOTFS_IMAGE_SEEK ))
			self.Console.eBatch(self.commandMB, self.Stage3Complete, debug=False)

		elif 'emmcimg' in getImageFileSystem():
			print '[ImageManager] osmio4k: EMMC Detected.'		# osmio4k receiver with multiple eMMC partitions in class
			IMAGE_ROOTFS_ALIGNMENT=1024
			BOOT_PARTITION_SIZE=3072
			KERNEL_PARTITION_SIZE=8192
			ROOTFS_PARTITION_SIZE=1898496				
			EMMC_IMAGE_SIZE=7634944
			KERNEL_PARTITION_OFFSET = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			ROOTFS_PARTITION_OFFSET = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SECOND_KERNEL_PARTITION_OFFSET = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			SECOND_ROOTFS_PARTITION_OFFSET = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			THIRD_KERNEL_PARTITION_OFFSET = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			THIRD_ROOTFS_PARTITION_OFFSET = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			FOURTH_KERNEL_PARTITION_OFFSET = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			FOURTH_ROOTFS_PARTITION_OFFSET = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SWAP_PARTITION_OFFSET = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			EMMC_IMAGE = "%s/%s"% (self.WORKDIR,self.EMMCIMG)
			EMMC_IMAGE_SEEK = int(EMMC_IMAGE_SIZE) * 1024
			self.commandMB.append('dd if=/dev/zero of=%s bs=1 count=0 seek=%s' % (EMMC_IMAGE, EMMC_IMAGE_SEEK))
			self.commandMB.append('parted -s %s mklabel gpt' %EMMC_IMAGE)
			PARTED_END_BOOT = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart boot fat16 %s %s' % (EMMC_IMAGE, IMAGE_ROOTFS_ALIGNMENT, PARTED_END_BOOT ))
			PARTED_END_KERNEL1 = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel1 %s %s' % (EMMC_IMAGE, KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL1 ))
			PARTED_END_ROOTFS1 = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs1 ext4 %s %s' % (EMMC_IMAGE, ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS1 ))
			PARTED_END_KERNEL2 = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel2 %s %s' % (EMMC_IMAGE, SECOND_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL2 ))
			PARTED_END_ROOTFS2 = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs2 ext4 %s %s' % (EMMC_IMAGE, SECOND_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS2 ))
			PARTED_END_KERNEL3 = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel3 %s %s' % (EMMC_IMAGE, THIRD_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL3 ))
			PARTED_END_ROOTFS3 = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs3 ext4 %s %s' % (EMMC_IMAGE, THIRD_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS3 ))
			PARTED_END_KERNEL4 = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart kernel4 %s %s' % (EMMC_IMAGE, FOURTH_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL4 ))
			PARTED_END_ROOTFS4 = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append('parted -s %s unit KiB mkpart rootfs4 ext4 %s %s' % (EMMC_IMAGE, FOURTH_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS4 ))

			BOOT_IMAGE_BS = int(IMAGE_ROOTFS_ALIGNMENT) * 1024
			self.commandMB.append('dd conv=notrunc if=/dev/%s of=%s seek=1 bs=%s' % (self.MTDBOOT, EMMC_IMAGE, BOOT_IMAGE_BS ))
			KERNEL_IMAGE_BS = int(KERNEL_PARTITION_OFFSET) * 1024
			self.commandMB.append('dd conv=notrunc if=/dev/%s of=%s seek=1 bs=%s' % (self.MTDKERNEL, EMMC_IMAGE, KERNEL_IMAGE_BS ))
			ROOTFS_IMAGE_BS = int(ROOTFS_PARTITION_OFFSET) * 1024
			self.commandMB.append('dd if=/dev/%s of=%s seek=1 bs=%s' % (self.MTDROOTFS, EMMC_IMAGE, ROOTFS_IMAGE_BS ))
			self.Console.eBatch(self.commandMB, self.Stage3Complete, debug=False)

		elif getImageFileSystem() in ('octagonemmc', 'gigablueemmc'):
			print '[ImageManager] /Trio4K sf8008: Making emmc_partitions.xml'
			f = open("%s/emmc_partitions.xml" %self.WORKDIR, "w")
			f.write('<?xml version="1.0" encoding="GB2312" ?>\n')
			f.write('<Partition_Info>\n')
			f.write('<Part Sel="1" PartitionName="fastboot" FlashType="emmc" FileSystem="none" Start="0" Length="1M" SelectFile="fastboot.bin"/>\n')
			f.write('<Part Sel="1" PartitionName="bootargs" FlashType="emmc" FileSystem="none" Start="1M" Length="1M" SelectFile="bootargs.bin"/>\n')
			f.write('<Part Sel="1" PartitionName="bootimg" FlashType="emmc" FileSystem="none" Start="2M" Length="1M" SelectFile="boot.img"/>\n')
			f.write('<Part Sel="1" PartitionName="baseparam" FlashType="emmc" FileSystem="none" Start="3M" Length="3M" SelectFile="baseparam.img"/>\n')
			f.write('<Part Sel="1" PartitionName="pqparam" FlashType="emmc" FileSystem="none" Start="6M" Length="4M" SelectFile="pq_param.bin"/>\n')
			f.write('<Part Sel="1" PartitionName="logo" FlashType="emmc" FileSystem="none" Start="10M" Length="4M" SelectFile="logo.img"/>\n')
			f.write('<Part Sel="1" PartitionName="deviceinfo" FlashType="emmc" FileSystem="none" Start="14M" Length="4M" SelectFile="deviceinfo.bin"/>\n')
			f.write('<Part Sel="1" PartitionName="loader" FlashType="emmc" FileSystem="none" Start="26M" Length="32M" SelectFile="apploader.bin"/>\n')
			f.write('<Part Sel="1" PartitionName="kernel" FlashType="emmc" FileSystem="none" Start="66M" Length="32M" SelectFile="vmlinux.bin"/>\n')
			f.write('<Part Sel="1" PartitionName="rootfs" FlashType="emmc" FileSystem="ext3/4" Start="98M" Length="7000M" SelectFile="rootfs.ext4"/>\n')
			f.write('</Partition_Info>\n')
			f.close()
			print '[ImageManager] Trio4K sf8008: Executing', '/usr/bin/mkupdate -s 00000003-00000001-01010101 -f %s/emmc_partitions.xml -d %s/%s' % (self.WORKDIR,self.WORKDIR,self.EMMCIMG) 
			self.commandMB.append('echo " "')
			self.commandMB.append('echo "Create: fastboot dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p1 of=%s/fastboot.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: bootargs dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p2 of=%s/bootargs.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: boot dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p3 of=%s/boot.img" % self.WORKDIR)
			self.commandMB.append('echo "Create: baseparam.dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p4 of=%s/baseparam.img" % self.WORKDIR)
			self.commandMB.append('echo "Create: pq_param dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p5 of=%s/pq_param.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: logo dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p6 of=%s/logo.img" % self.WORKDIR)
			self.commandMB.append('echo "Create: deviceinfo dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p7 of=%s/deviceinfo.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: apploader dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p8 of=%s/apploader.bin" % self.WORKDIR)
			self.commandMB.append('echo "Pickup previous created: kernel dump"')
			self.commandMB.append('echo "Create: rootfs dump"')
			self.commandMB.append("dd if=/dev/zero of=%s/rootfs.ext4 seek=524288 count=0 bs=1024" % (self.WORKDIR))
			self.commandMB.append("mkfs.ext4 -F -i 4096 %s/rootfs.ext4 -d %s/root" %(self.WORKDIR, self.TMPDIR))
			self.commandMB.append('echo " "')
			self.commandMB.append('echo "Create: Trio4K Sf8008 Recovery Fullbackup %s"'% (self.EMMCIMG))
			self.commandMB.append('echo " "')
			self.commandMB.append('/usr/sbin/mkupdate -s 00000003-00000001-01010101 -f %s/emmc_partitions.xml -d %s/%s' % (self.WORKDIR,self.WORKDIR,self.EMMCIMG))
			self.Console.eBatch(self.commandMB, self.Stage3Complete, debug=False)
		elif 'hdfastboot8gb' in getImageFileSystem():
			self.commandMB.append('echo " "')
			self.commandMB.append('echo "' + _("Create:") + " fastboot dump" + '"')
			self.commandMB.append("dd if=/dev/mmcblk0p1 of=%s/fastboot.bin" % self.WORKDIR)
			self.commandMB.append('echo "' + _("Create:") + " bootargs dump" + '"')
			self.commandMB.append("dd if=/dev/mmcblk0p2 of=%s/bootargs.bin" % self.WORKDIR)
			self.commandMB.append('echo "' + _("Create:") + " bootoptions dump" + '"')
			self.commandMB.append("dd if=/dev/mmcblk0p5 of=%s/bootoptions.bin" % self.WORKDIR)
			self.commandMB.append('echo "' + _("Create:") + " baseparam dump" + '"')
			self.commandMB.append("dd if=/dev/mmcblk0p6 of=%s/baseparam.bin" % self.WORKDIR)
			self.commandMB.append('echo "' + _("Create:") + " pq_param dump" + '"')
			self.commandMB.append("dd if=/dev/mmcblk0p7 of=%s/pq_param.bin" % self.WORKDIR)
			self.commandMB.append('echo "' + _("Create:") + " logo dump" + '"')
			self.commandMB.append("dd if=/dev/mmcblk0p8 of=%s/logo.bin" % self.WORKDIR)
			self.commandMB.append('echo "' + _("Create:") + " rootfs dump" + '"')
			self.commandMB.append("dd if=/dev/zero of=%s/rootfs.ext4 seek=1048576 count=0 bs=1024" % (self.WORKDIR))
			self.commandMB.append("mkfs.ext4 -F -i 4096 %s/rootfs.ext4 -d /tmp/bi/root" % (self.WORKDIR))
			self.commandMB.append('echo " "')
			self.commandMB.append('echo "' + _("Create: Recovery Fullbackup %s")% (self.EMMCIMG) + '"')
			self.commandMB.append('echo " "')
			self.commandMB.append('%s -zv %s/rootfs.ext4 %s/%s' % (self.FASTBOOT,self.WORKDIR,self.WORKDIR,self.EMMCIMG))
		else:
			self.Stage3Completed = True
			print '[ImageManager] Stage3 bypassed: Complete.'

	def Stage3Complete(self, extra_args=None):
		self.Stage3Completed = True
		print '[ImageManager] Stage3: Complete.'

	def doBackup4(self):
		print '[ImageManager] Stage4: Unmounting and removing tmp system'
		if path.exists(self.TMPDIR + '/root') and path.ismount(self.TMPDIR + '/root'):
			self.command = 'umount ' + self.TMPDIR + '/root && rm -rf ' + self.TMPDIR
			self.Console.ePopen(self.command, self.Stage4Complete)
		else:
			if path.exists(self.TMPDIR):
				rmtree(self.TMPDIR)
			self.Stage4Complete('pass', 0)

	def Stage4Complete(self, result, retval, extra_args=None):
		if retval == 0:
			self.Stage4Completed = True
			print '[ImageManager] Stage4: Complete.'

	def doBackup5(self):
		print '[ImageManager] Stage5: Moving from work to backup folders'
		if self.ROOTDEVTYPE in ('hdemmc', 'emmcimg') and path.exists('%s/%s' % (self.WORKDIR, self.EMMCIMG)):
			move('%s/%s' %(self.WORKDIR, self.EMMCIMG), '%s/%s' %(self.MAINDEST, self.EMMCIMG))

		if getImageFileSystem() in ('octagonemmc', 'gigablueemmc'):
			move('%s/%s' %(self.WORKDIR, self.EMMCIMG), '%s/%s' %(self.MAINDEST2, self.EMMCIMG))
			move('%s/%s' %(self.WORKDIR, "emmc_partitions.xml"), '%s/%s' %(self.MAINDEST, "emmc_partitions.xml"))

		if self.KERNELFSTYPE == 'bin' and path.exists('%s/vmlinux.bin' % self.WORKDIR):
			move('%s/vmlinux.bin' % self.WORKDIR, '%s/%s' % (self.MAINDEST, self.KERNELFILE))
		else:
			move('%s/vmlinux.gz' % self.WORKDIR, '%s/%s' % (self.MAINDEST, self.KERNELFILE))

		if getMachineBuild() in ("h9"):
			z = open('/proc/cmdline', 'r').read()
			if SystemInfo["HasMMC"] and "root=/dev/mmcblk0p1" in z: 
				move('%s/rootfs.tar.bz2' % self.WORKDIR, '%s/%s' % (self.MAINDEST, self.ROOTFSFILE))
			else:
				move('%s/rootfs.%s' % (self.WORKDIR, self.ROOTFSTYPE), '%s/%s' % (self.MAINDEST, self.ROOTFSFILE))
		else:
			move('%s/rootfs.%s' % (self.WORKDIR, self.ROOTFSTYPE), '%s/%s' % (self.MAINDEST, self.ROOTFSFILE))

		if getMachineBuild() in ("gb7252"):
			move('%s/%s' % (self.WORKDIR, self.GB4Kbin), '%s/%s' % (self.MAINDEST, self.GB4Kbin))
			move('%s/%s' % (self.WORKDIR, self.GB4Krescue), '%s/%s' % (self.MAINDEST, self.GB4Krescue))
			system('cp -f /usr/share/gpt.bin %s/gpt.bin' %(self.MAINDEST))
			print '[ImageManager] Stage5: Create: gpt.bin:',self.MODEL

		if getMachineBuild() in ("h9"):
			system('mv %s/fastboot.bin %s/fastboot.bin' %(self.WORKDIR, self.MAINDEST))
			system('mv %s/pq_param.bin %s/pq_param.bin' %(self.WORKDIR, self.MAINDEST))
			system('mv %s/bootargs.bin %s/bootargs.bin' %(self.WORKDIR, self.MAINDEST))
			system('mv %s/baseparam.bin %s/baseparam.bin' %(self.WORKDIR, self.MAINDEST))
			system('mv %s/logo.bin %s/logo.bin' %(self.WORKDIR, self.MAINDEST))

		if 'hdfastboot8gb' in getImageFileSystem():
			system('mv %s/baseparam.bin %s/bootoptions.bin' %(self.WORKDIR, self.MAINDEST))

		fileout = open(self.MAINDEST + '/imageversion', 'w')
		line = defaultprefix + '-' + getImageType() + '-backup-' + getImageVersion() + '.' + getImageBuild() + '-' + self.BackupDate
		fileout.write(line)
		fileout.close()
		if getBrandOEM() ==  'vuplus':
			if getMachineBuild() == 'vuzero':
				fileout = open(self.MAINDEST + '/force.update', 'w')
				line = "This file forces the update."
				fileout.write(line)
				fileout.close()
			else:
				fileout = open(self.MAINDEST + '/reboot.update', 'w')
				line = "This file forces a reboot after the update."
				fileout.write(line)
				fileout.close()
			imagecreated = True
		elif getBrandOEM() in ('xtrend', 'gigablue', 'octagon', 'odin', 'xp', 'ini'):
			if getBrandOEM() in ('xtrend', 'octagon', 'odin', 'ini'):
				fileout = open(self.MAINDEST + '/noforce', 'w')
				line = "rename this file to 'force' to force an update without confirmation"
				fileout.write(line)
				fileout.close()
			if getBrandOEM() in ('octagon') and SystemInfo["HasSDmmc"] and self.KERN == "mmc":
				fileout = open(self.MAINDEST + '/SDAbackup', 'w')
				line = "SF8008 indicate type of backup %s" %self.KERN
				fileout.write(line)
				fileout.close()
				self.session.open(MessageBox, _("Multiboot only able to restore this backup to mmc slot1"), MessageBox.TYPE_INFO, timeout=20)
			if path.exists('/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat'):
				copy('/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat', self.MAINDESTROOT + '/burn.bat')

		print '[ImageManager] Stage5: Removing Swap.'
		if path.exists(self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup"):
			system('swapoff ' + self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
			remove(self.swapdevice + config.imagemanager.folderprefix.value + '-' + getImageType() + "-swapfile_backup")
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		if (path.exists(self.MAINDEST + '/' + self.ROOTFSFILE) and path.exists(self.MAINDEST + '/' + self.KERNELFILE)) or (self.ROOTDEVTYPE == 'hdemmc' and path.exists('%s/disk.img' % self.MAINDEST)):
			for root, dirs, files in walk(self.MAINDEST):
				for momo in dirs:
					chmod(path.join(root, momo), 0644)
				for momo in files:
					chmod(path.join(root, momo), 0644)
			print '[ImageManager] Stage5: Image created in ' + self.MAINDESTROOT
			self.Stage5Complete()
		else:
			print "[ImageManager] Stage5: Image creation failed - e. g. wrong backup destination or no space left on backup device"
			self.BackupComplete()

	def Stage5Complete(self):
		self.Stage5Completed = True
		print '[ImageManager] Stage5: Complete.'

	def doBackup6(self):
		zipfolder = path.split(self.MAINDESTROOT)
		self.commands = []
		self.commands.append('cd ' + self.MAINDESTROOT + ' && zip -r ' + self.MAINDESTROOT + '.zip *')
		self.commands.append('rm -rf ' + self.MAINDESTROOT)
		self.Console.eBatch(self.commands, self.Stage6Complete, debug=True)

	def Stage6Complete(self, answer=None):
		self.Stage6Completed = True
		print '[ImageManager] Stage6: Complete.'

	def BackupComplete(self, answer=None):
		#    trim the number of backups kept...
		import fnmatch
		try:
			if config.imagemanager.number_to_keep.value > 0 \
			 and path.exists(self.BackupDirectory): # !?!
				images = listdir(self.BackupDirectory)
				patt = config.imagemanager.folderprefix.value + '-*.zip'
				emlist = []
				for fil in images:
					if fnmatch.fnmatchcase(fil, patt):
						emlist.append(fil)
				# sort by oldest first...
				emlist.sort(key=lambda fil: path.getmtime(self.BackupDirectory + fil))
				# ...then, if we have too many, remove the <n> newest from the end
				# and delete what is left
				if len(emlist) > config.imagemanager.number_to_keep.value:
					emlist = emlist[0:len(emlist)-config.imagemanager.number_to_keep.value]
					for fil in emlist:
						remove(self.BackupDirectory + fil)
		except:
			pass
		if config.imagemanager.schedule.value:
			atLeast = 60
			autoImageManagerTimer.backupupdate(atLeast)
		else:
			autoImageManagerTimer.backupstop()

class ImageManagerDownload(Screen):
	skin = """
	<screen name="VIXImageManager" position="center,center" size="560,400">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" />
		<widget name="lab1" position="0,50" size="560,50" font="Regular; 18" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="10,105" size="540,260" scrollbarMode="showOnDemand" />
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session, menu_path, BackupDirectory, url):
		Screen.__init__(self, session)
		screentitle = _("Downloads")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		self.Pli = False
		self.urli = url
		import urllib2, json
		self.BackupDirectory = BackupDirectory
		self['lab1'] = Label(_("Select an image to download:"))
		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("Download"))
		self.Downlist = []
		self.jsonlist = {}
		self.imagesList = {}
		self.setIndex = 0
		self.expanded = []
		if "pli" in self.urli:
			self.Pli = True
			self["list"] = ChoiceList(list=[ChoiceEntryComponent('',((_("Retrieving image list - Please wait...")), "Waiter"))])
		else:
			self['list'] = MenuList(self.Downlist)
		self['ImageDown'] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "KeyboardInputActions", "MenuActions"],
									  {
										'cancel': self.close,
										'red': self.close,
										'green': self.keyDownload,
										'ok': self.keyDownload,
										"up": self.keyUp,
										"down": self.keyDown,
										"left": self.keyLeft,
										"right": self.keyRight,
										"upRepeated": self.keyUp,
										"downRepeated": self.keyDown,
										"leftRepeated": self.keyLeft,
										"rightRepeated": self.keyRight,
										"menu": self.close,
									  }, -1)
		if self.Pli:
			self.delay = eTimer()
			self.delay.callback.append(self.getImagesList)
			self.delay.start(0, True)
		else:
			self.populate_DownList()


	def populate_DownList(self):
		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			from bs4 import BeautifulSoup
			supportedMachines = {
				'axodinc'         : 'Opticum-AX-ODIN-DVBC-1',
				'dinobot4kmini'   : 'dinobot4kmini',
				'dinobot4kplus'   : 'dinobot4kplus',
				'et10000'         : 'ET-10x00',
				'et4x00'          : 'ET-4x00',
				'et5x00'          : 'ET-5x00',
				'et6x00'          : 'ET-6x00',
				'et7x00'          : 'ET-7x00',
				'et8000'          : 'ET-8000',
				'et8500'          : 'ET-8500',
				'et9x00'          : 'ET-9x00',
				'formuler4turbo'  : 'Formuler4turbo',
				'formuler1'       : 'Formuler1',
				'formuler1tc'     : 'Formuler1tc',
				'gb800se'         : 'GiGaBlue-HD800SE',
				'gb800seplus'     : 'GiGaBlue-HD800SE-PLUS',
				'gb800ue'         : 'GiGaBlue-HD800UE',
				'gb800ueplus'     : 'GiGaBlue-HD800UE-PLUS',
				'gbquad'          : 'GiGaBlue-HD-QUAD',
				'gbquadplus'      : 'GiGaBlue-HD-QUAD-PLUS',
				'gbquad4k'	  : 'gbquad4k',	
				'gbue4k'          : 'gbue4k',
				'gbmv200' 	  : 'GiGaBlue-Trio-4K',				
				'gbultraue'       : 'GiGaBlue-HD-ULTRA-UE',
				'gbx1'            : 'GiGaBlue-HD-X1',
				'gbx2'            : 'GiGaBlue-HD-X2',
				'gbx3'            : 'GiGaBlue-HD-X3',
				'gbx3h'           : 'GiGaBlue-HD-X3H',
				'iqonios100hd'    : 'iqon-IOS-100HD',
				'iqonios200hd'    : 'iqon-IOS-200HD',
				'iqonios300hd'    : 'iqon-IOS-300HD',
				'ixusszero'       : 'Medialink-IXUSS-ZERO',
				'maram9'          : 'Mara-M9',
				'mbhybrid'        : 'Miraclebox-Mini-Hybrid',
				'mbmicro'         : 'Miraclebox-Micro',
				'mbmicrov2'       : 'Miraclebox-Microv2',
				'mbmini'          : 'Miraclebox-Mini',
				'mbminiplus'      : 'Miraclebox-MiniPlus',
				'mbtwin'          : 'Miraclebox-Twin',
				'mbtwinplus'      : 'Miraclebox-Twinplus',
				'mbultra'         : 'Miraclebox-Ultra',
				'mutant11'        : 'Mutant-HD11',
				'mutant1200'      : 'Mutant-HD1200',
				'mutant1500'      : 'Mutant-HD1500',
				'mutant2400'      : 'Mutant-HD2400',
				'mutant500c'      : 'Mutant-HD500C',
				'mutant51'        : 'Mutant-HD51',
				'osmega'          : 'OS-mega',
				'osmini'          : 'OS-mini',
				'osminiplus'      : 'OS-miniplus',
				'osnino'          : 'OS-nino',
				'osmio4k'         : 'OS-mio4k',
				'osninoplus'      : 'OS-ninoplus',
				'osninopro'       : 'OS-ninopro',				
				'qb800solo'       : 'GiGaBlue-HD800Solo',
				'sf8'             : 'OCTAGON-SF8-HD',
				'sf128'           : 'OCTAGON-SF128',
				'sf138'           : 'OCTAGON-SF138',
				'sf228'           : 'OCTAGON-SF228',
				'sf4008'          : 'OCTAGON-SF4008',
				'sf8008'          : 'OCTAGON-SF8008',
				'spycat'          : 'Spycat',
				'tiviaraplus'     : 'TiviarAlphaPlus',
				'tm2t'            : 'TM-2T',
				'tmnano'          : 'TM-Nano-OE',
				'tmnano2super'    : 'TM-Nano2-Super',
				'tmnano2t'        : 'TM-Nano-2T',
				'tmnano3t'        : 'TM-Nano-3T',
				'tmnanose'        : 'TM-Nano-SE',
				'tmnanosecombo'   : 'TM-Nano-SE-Combo',
				'tmnanosem2'      : 'TM-Nano-SE-M2',
				'tmnanosem2plus'  : 'TM-Nano-SE-M2-Plus',
				'tmnanom3'        : 'TM-Nano-M3',
				'tmnanoseplus'    : 'TM-Nano-SE-Plus',
				'tmsingle'        : 'TM-Single',
				'tmtwin'          : 'TM-Twin-OE',
				'tmtwin4k'        : 'TM-Twin-4K',
				'uniboxhde'       : 'Venton-Unibox-HDeco-PLUS',
				'ventonhdx'       : 'Venton-Unibox-HDx',
				'vipercombohdd'   : 'Amiko-Viper-Combo-HDD',				
				'vuduo'           : 'Vu+Duo',
				'vuduo2'          : 'Vu+Duo2',
				'vuduo4k'         : 'Vu+Duo4k',				
				'vusolo'          : 'Vu+Solo',
				'vusolo2'         : 'Vu+Solo2',
				'vusolo4k'        : 'Vu+Solo4K',
				'vusolose'        : 'Vu+Solo-SE',
				'vuultimo'        : 'Vu+Ultimo',
				'vuultimo4k'      : 'Vu+Ultimo4K',
				'vuuno'           : 'Vu+Uno',
				'vuuno4k'         : 'Vu+Uno4K',
				'vuuno4kse'       : 'Vu+Uno4KSE',
				'vuzero'          : 'Vu+Zero',
				'vuzero4k'        : 'Vu+Zero4K',
				'xp1000max'       : 'MaxDigital-XP1000',
				'xp1000plus'      : 'OCTAGON-XP1000PLUS',
				'xpeedlx'         : 'GI-Xpeed-LX',
				'xpeedlx3'        : 'GI-Xpeed-LX3',
				'zgemmah7'        : 'Zgemma-H7',
				'zgemmah9s'       : 'Zgemma-H9S',
				'zgemmah92s'      : 'Zgemma-H92S',
				'zgemmah92h'      : 'Zgemma-H92H',				
				'zgemmah9t'       : 'Zgemma-H9T'				
			}

			if "atv" in self.urli:
				self.urlb = '%s/index.php?open=%s' % (self.urli, getMachineMake())
			else:
				try:
					self.boxtype = supportedMachines[getMachineMake()]
				except:
					self.session.open(MessageBox, _("%s" % getMachineMake()), MessageBox.TYPE_INFO, timeout=15)
					print "[ImageManager][populate_List] the %s is not currently supported by OpenViX." % getMachineMake()
					self.boxtype = 'UNKNOWN'
				self.urlb = self.urli+self.boxtype+'/'

			conn = urllib2.urlopen(self.urlb)
			html = conn.read()

			soup = BeautifulSoup(html)
			links = soup.find_all('a')

			del self.Downlist[:]
			for tag in links:
				link = tag.get('href',None)
				if link != None and link.endswith('zip') and link.find(getMachineMake()) != -1:
					self.Downlist.append(str(link))

			self.Downlist.sort()
			self.Downlist.reverse()
		except:
			self['ImageDown'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
										  {
										  'cancel': self.close,
										  'red': self.close,
										  }, -1)
			self.Downlist.append(" ")
			self["list"].setList(self.Downlist)
			self["list"].show()

	def getImagesList(self):
		model = HardwareInfo().get_device_name()
		print "[ImageManager][imagelist] model %s " %model
		list = []
		if not self.imagesList:
			if not self.jsonlist:
				try:
					self.jsonlist = dict(json.load(urllib2.urlopen('http://downloads.openpli.org/json/%s' % model)))
				except:
					pass
			self.imagesList = self.jsonlist
		for catagorie in reversed(sorted(self.imagesList.keys())):
			if catagorie in self.expanded:
				list.append(ChoiceEntryComponent('expanded',((str(catagorie)), "Expander")))
				for image in reversed(sorted(self.imagesList[catagorie].keys())):
					list.append(ChoiceEntryComponent('verticalline',((str(self.imagesList[catagorie][image]['name'])), str(self.imagesList[catagorie][image]['link']))))
			else:
				for image in self.imagesList[catagorie].keys():
					list.append(ChoiceEntryComponent('expandable',((str(catagorie)), "Expander")))
					break
		if list:
			self["list"].setList(list)
			if self.setIndex:
				self["list"].moveToIndex(self.setIndex if self.setIndex < len(list) else len(list) - 1)
				if self["list"].l.getCurrentSelection()[0][1] == "Expander":
					self.setIndex -= 1
					if self.setIndex:
						self["list"].moveToIndex(self.setIndex if self.setIndex < len(list) else len(list) - 1)
				self.setIndex = 0
			self.selectionChanged()
		else:
			self.session.openWithCallback(self.close, MessageBox, _("Cannot find images - please try later"), type=MessageBox.TYPE_ERROR, timeout=3)

	def selectionChanged(self):
		currentSelected = self["list"].l.getCurrentSelection()
		if self.Pli:
			if currentSelected[0][1] == "Waiter":
				self["key_green"].setText("")
			else:
				if currentSelected[0][1] == "Expander":
					self["key_green"].setText(_("Compress") if currentSelected[0][0] in self.expanded else _("Expand"))
				else:
					self["key_green"].setText(_("DownLoad"))

	def keyLeft(self):
		self["list"].instance.moveSelection(self["list"].instance.pageUp)
		self.selectionChanged()

	def keyRight(self):
		self["list"].instance.moveSelection(self["list"].instance.pageDown)
		self.selectionChanged()

	def keyUp(self):
		self["list"].instance.moveSelection(self["list"].instance.moveUp)
		self.selectionChanged()

	def keyDown(self):
		self["list"].instance.moveSelection(self["list"].instance.moveDown)
		self.selectionChanged()

	def keyDownload(self):
		if self.Pli:
			currentSelected = self["list"].l.getCurrentSelection()
			if currentSelected[0][1] == "Expander":
				if currentSelected[0][0] in self.expanded:
					self.expanded.remove(currentSelected[0][0])
				else:
					self.expanded.append(currentSelected[0][0])
				self.getImagesList()
			elif currentSelected[0][1] != "Waiter":
				self.sel = currentSelected[0][0]
				if self.sel:
					message = _("Are you sure you want to download this image:\n ") + self.sel
					ybox = self.session.openWithCallback(self.doDownload, MessageBox, message, MessageBox.TYPE_YESNO)
					ybox.setTitle(_("Download confirmation"))
				else:
					self.session.open(MessageBox, _("There is no image to download."), MessageBox.TYPE_INFO, timeout=10)
		else:
			self.sel = self['list'].getCurrent()
			if self.sel:
				message = _("Are you sure you want to download this image:\n ") + self.sel
				ybox = self.session.openWithCallback(self.doDownload, MessageBox, message, MessageBox.TYPE_YESNO)
				ybox.setTitle(_("Download confirmation"))
			else:
				self.session.open(MessageBox, _("There is no image to download."), MessageBox.TYPE_INFO, timeout=10)

	def doDownload(self, answer):
		if answer is True:
			selectedimage = self['list'].getCurrent()
			if self.Pli:
				currentSelected = self["list"].l.getCurrentSelection()
				selectedimage = currentSelected[0][0]
				fileurl = currentSelected[0][1]
				fileloc = self.BackupDirectory + selectedimage
				print "[ImageManager][OpenPli] detected %s is passed url for list image." % fileurl
			elif "atv" in self.urli:
				fileloc = self.BackupDirectory + selectedimage.split("/")[1]
				fileurl = self.urli + selectedimage
				print "[ImageManager][OpenATV] detected %s is passed url for list image." % fileurl
			else:
				fileloc = self.BackupDirectory + selectedimage
				fileurl = self.urlb + selectedimage
				print "[ImageManager][url plus boxtype] %s is passed url for image." % fileurl
			Tools.CopyFiles.downloadFile(fileurl, fileloc, selectedimage.replace('_usb',''))
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Downloading")):
					break
			self.showJobView(job)

	def showJobView(self, job):
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, backgroundable=True, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background