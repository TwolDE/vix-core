from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Button import Button
from Components.Sources.StaticText import StaticText
from Components import Harddisk
from Components.SystemInfo import SystemInfo
from os import path, listdir, system
from boxbranding import getMachineBuild
#
#        Thanks to OpenATV Team for supplying most of this code
#
class MultiBoot(Screen):

	skin = """
	<screen name="MultiBoot" position="center,center" size="560,400" title="MultiBoot STARTUP Selector">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" />
		<widget source="config" render="Label" position="150,150" size="580,150" halign="center" valign="center" font="Regular; 30" />
		<widget source="options" render="Label" position="150,400" size="580,100" halign="center" valign="center" font="Regular; 24" />
		<widget name="description" position="150,650" size="580,100" halign="center" valign="center" font="Regular; 24" />
		<ePixmap position="555,217" size="35,25" zPosition="2" pixmap="/usr/share/enigma2/skin_default/buttons/key_info.png" alphatest="blend" />
		<applet type="onLayoutFinish">
		</applet>
	</screen>"""

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle =  _("MultiBoot STARTUP Selector")
		self.skinName = ["MultiBoot"]

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

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self["key_yellow"] = Button(_("Rename"))
		self["config"] = StaticText()
		self["options"] = StaticText()
		self["description"] = Label()
		if SystemInfo["HaveMultiBootHD"]:
			self["actions"] = ActionMap(["WizardActions", "SetupActions", "ColorActions"],
			{
				"left": self.left,
				"right": self.right,
				"up": self.up,
				"down": self.down,
				"green": self.save,
				"red": self.cancel,
				"cancel": self.cancel,
				"ok": self.save,
			}, -2)
			self.getCurrent()
			self.onLayoutFinish.append(self.layoutFinished)
		elif SystemInfo["HaveMultiBootGB"]:
			self.selection = 0
			if path.exists('/boot/STARTUP'):
				f = open('/boot/STARTUP', 'r')
				f.seek(22)
				image = f.read(1) 
				f.close()
				self["description"].setText(_("Current Startup: STARTUP_%s") %(image))
			self.list = self.list_files("/boot")
			self.startupGB()
			self["actions"] = ActionMap(["WizardActions", "SetupActions", "ColorActions"],
			{
				"left": self.left,
				"right": self.right,
				"green": self.saveGB,
				"red": self.cancel,
				"cancel": self.cancel,
				"ok": self.saveGB,
			}, -2)
			self.onLayoutFinish.append(self.layoutFinished)


	def writeFile(self, FILE, DATA):
		try:
			f = open(FILE, 'w')
			f.write(DATA)
			f.close()
			return True
		except IOError:
			print "[MultiBootStartup] write error file: %s" %FILE 
			return False

	def readlineFile(self, FILE):
		data = ''
		if path.isfile(FILE):
			f = open(FILE, 'r')
			data = f.readline().replace('\n', '')
			f.close()
		return data

	def getCurrent(self):
		'''
		#HD51 default
		Image 1: boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait'
		Image 2: boot emmcflash0.kernel2 'root=/dev/mmcblk0p5 rw rootwait'
		Image 3: boot emmcflash0.kernel3 'root=/dev/mmcblk0p7 rw rootwait'
		Image 4: boot emmcflash0.kernel4 'root=/dev/mmcblk0p9 rw rootwait'
		#HD51 options
		Standard:     hd51_4.boxmode=1 (or no option)
		Experimental: hd51_4.boxmode=12
		#example
		boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait hd51_4.boxmode=1'
		
		'''

		self.optionsList = (('boxmode=1', _('2160p60 without PiP (Standard)')), ('boxmode=12', _('2160p50 with PiP (Experimental)')))
		self.bootloaderList = ('v1.07-r19', 'v1.07-r21', 'v1.07-r35')

		#for compatibility to old or other images set 'self.enable_bootnamefile = False'
		#if 'False' and more as on file with same kernel exist is possible no exact matching found (only to display)
		self.enable_bootnamefile = False
		if not self.enable_bootnamefile and path.isfile('/boot/bootname'):
			system("rm -f /boot/bootname")

		self.list = self.list_files("/boot")
		self.option_enabled = self.readlineFile('/sys/firmware/devicetree/base/bolt/tag').replace('\x00', '') in self.bootloaderList

		boot = self.readlineFile('/boot/STARTUP')
		bootname = self.readlineFile('/boot/bootname').split('=')

		self.selection = None
		self.option = 0

		#read name from bootname file
		if len(bootname) == 2:
			idx = 0
			for x in self.list:
				if x == bootname[1]:
					self.selection = idx
					bootname = x
					break
				idx += 1
			if self.selection is None:
				idx = 0
				for x in self.list:
					if x == bootname[0]:
						self.selection = idx
						bootname = x
						break
					idx += 1
		#verify bootname
		if bootname in self.list:
			line = self.readlineFile('/boot/%s' %bootname)
			if line[22:23] != boot[22:23]:
				self.selection = None
		else:
			self.selection = None
		#bootname searching ...
		if self.selection is None:
			idx = 0
			for x in self.list:
				line = self.readlineFile('/boot/%s' %x)
				if line[22:23] == boot[22:23]:
					bootname = x
					self.selection = idx
					break
				idx += 1
		#bootname not found
		if self.selection is None:
			bootname = _('unknown')
			self.selection = 0
		self.bootname = bootname

		#read current boxmode
		try:
			bootmode = boot.split('rootwait',1)[1].split('boxmode',1)[1].split("'",1)[0].split('=',1)[1].replace(' ','')
		except IndexError:
			bootmode = ""
		#find and verify current boxmode
		if self.option_enabled:
			idx = 0
			for x in self.optionsList:
				if bootmode and bootmode == x[0].split('=')[1]:
					self.option = idx
					break
				elif x[0] + "'" in boot or x[0] + " " in boot:
					self.option = idx
					break
				idx += 1

		if bootmode and bootmode != self.optionsList[self.option][0].split('=')[1]:
			bootoption = ', boxmode=' + bootmode + _(" (unknown mode)")
		elif self.option_enabled:
			bootoption = ', ' + self.optionsList[self.option][0]
		else:
			bootoption = ''
		try:
			image = 'Image %s' %(int(boot[22:23]))
		except:
			image = _("Unable to read image number")

		self.startup()
		self.startup_option()
		self["description"].setText(_("Current Bootsettings: %s (%s)%s") %(bootname,image,bootoption))

	def layoutFinished(self):
		self.setTitle(self.title)

	def startup_option(self):
		if self.option_enabled:
			self["options"].setText(_("Select Boot option using up/down cursors:\n %s") %self.optionsList[self.option][1])
		elif 'up' in self["actions"].actions:
			self["options"].setText(_("Select Bootoption: not supported - see info"))
			del self["actions"].actions['up']
			del self["actions"].actions['down']

	def startup(self):
		if len(self.list):
			self["config"].setText(_("Select Image using < > cursors:\n %s") %self.list[self.selection])
		elif 'left' in self["actions"].actions:
			self["config"].setText(_("Select Image: %s") %_("no image found"))
			del self["actions"].actions['left']
			del self["actions"].actions['right']
			del self["actions"].actions['green']
			del self["actions"].actions['yellow']
			del self["actions"].actions['ok']

	def checkBootEntry(self, ENTRY):
		try:
			ret = False
			temp = ENTRY.split(' ')
			#read kernel, root as number and device name
			kernel = int(temp[1].split("emmcflash0.kernel")[1])
			root = int(temp[4].split("root=/dev/mmcblk0p")[1])
			device = temp[4].split("=")[1]
			#read boxmode and new boxmode settings
			cmdx = 7
			cmd4 = "rootwait'"
			bootmode = '1'
			if 'boxmode' in ENTRY:
				cmdx = 8
				cmd4 = "rootwait"
				bootmode = temp[7].split("%s_4.boxmode=" %getMachineBuild())[1].replace("'",'')
			setmode = self.optionsList[self.option][0].split('=')[1]
			print "[MultiBootStartup] ENTRY %s cmdx %s cmd4 %s bootmode %s setmode %s" %(ENTRY, cmdx, cmd4, bootmode, setmode)
			if self.option_enabled: 
				print "[MultiBootStartup] self.option_enabled TRUE"
			#verify entries
			if cmdx != len(temp) or 'boot' != temp[0] or 'rw' != temp[5] or cmd4 != temp[6] or kernel != root-kernel-1:
				print "[MultiBootStartup] Command line in '/boot/STARTUP' - problem with not matching entries!"
				ret = True
			#verify length
			elif ('boxmode' not in ENTRY and len(ENTRY) > 96) or ('boxmode' in ENTRY and len(ENTRY) > 115):
				print "[MultiBootStartup] Command line in '/boot/STARTUP' - problem with line length!"
				ret = True
			#verify boxmode
			elif bootmode != setmode and not self.option_enabled:
				print "[MultiBootStartup] Command line in '/boot/STARTUP' - problem with unsupported boxmode!"
				ret = True
			#verify device
			elif not device in Harddisk.getextdevices("ext4"):
				print "[MultiBootStartup] Command line in '/boot/STARTUP' - boot device not exist!"
				ret = True
		except:
			print "[MultiBootStartup] Command line in '/boot/STARTUP' - unknown problem!"
			ret = True
		return ret

	def save(self):
		print "[MultiBootStartup] select new startup: ", self.list[self.selection]
		ret = system("cp -f '/boot/%s' /boot/STARTUP" %self.list[self.selection])
		if ret:
			self.session.open(MessageBox, _("File '/boot/%s' copy to '/boot/STARTUP' failed!") %self.list[self.selection], MessageBox.TYPE_ERROR)
			self.getCurrent()
			return

		writeoption = already = failboot = False
		newboot = boot = self.readlineFile('/boot/STARTUP')

		if self.checkBootEntry(boot):
			failboot = True
		elif self.option_enabled:
			for x in self.optionsList:
				if (x[0] + "'" in boot or x[0] + " " in boot) and x[0] != self.optionsList[self.option][0]:
					newboot = boot.replace(x[0],self.optionsList[self.option][0])
					if self.optionsList[self.option][0] == "boxmode=1":
						newboot = newboot.replace("520M@248M", "440M@328M")
						newboot = newboot.replace("200M@768M", "192M@768M")
					elif self.optionsList[self.option][0] == "boxmode=12":
						newboot = newboot.replace("440M@328M", "520M@248M")
						newboot = newboot.replace("192M@768M", "200M@768M")
					writeoption = True
					break
				elif (x[0] + "'" in boot or x[0] + " " in boot) and x[0] == self.optionsList[self.option][0]:
					already = True
					break
			if not (writeoption or already):
				if "boxmode" in boot:
					failboot = True
				elif self.option:
					newboot = boot.replace("rootwait", "rootwait %s_4.%s" %(getMachineBuild(), self.optionsList[self.option][0]))
					if self.optionsList[self.option][0] == "boxmode=1":
						newboot = newboot.replace("520M@248M", "440M@328M")
						newboot = newboot.replace("200M@768M", "192M@768M")
					elif self.optionsList[self.option][0] == "boxmode=12":
						newboot = newboot.replace("440M@328M", "520M@248M")
						newboot = newboot.replace("192M@768M", "200M@768M")
					writeoption = True

		if self.enable_bootnamefile:
			if failboot:
				self.writeFile('/boot/bootname', 'STARTUP_1=STARTUP_1')
			else:
				self.writeFile('/boot/bootname', '%s=%s' %('STARTUP_%s' %getMachineBuild() ,boot[22:23], self.list[self.selection]))

		message = _("Do you want to reboot now with selected image?")
		if failboot:
			print "[MultiBootStartup] wrong bootsettings: " + boot
			if '/dev/mmcblk0p3' in Harddisk.getextdevices("ext4"):
				if self.writeFile('/boot/STARTUP', "boot emmcflash0.kernel1 'brcm_cma=440M@328M brcm_cma=192M@768M root=/dev/mmcblk0p3 rw rootwait'"):
					txt = _("Next boot will start from Image 1.")
				else:
					txt =_("Can not repair file %s") %("'/boot/STARTUP'") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
			else:
				txt = _("Alternative Image 1 partition for boot repair not found.") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
			message = _("Wrong Bootsettings detected!") + "\n\n%s\n\n%s\n" %(boot, txt) + _("Do you want to reboot now?")
		elif writeoption:
			if not self.writeFile('/boot/STARTUP', newboot):
				txt = _("Can not write file %s") %("'/boot/STARTUP'") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
				message = _("Write error!") + "\n\n%s\n\n%s\n" %(boot, txt) + _("Do you want to reboot now?")

		#verify boot
		if failboot or writeoption:
			boot = self.readlineFile('/boot/STARTUP')
			if self.checkBootEntry(boot):
				txt = _("Error in file %s") %("'/boot/STARTUP'") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
				message = _("Command line error!") + "\n\n%s\n\n%s\n" %(boot, txt) + _("Do you want to reboot now?")

		self.session.openWithCallback(self.restartBOX,MessageBox, message, MessageBox.TYPE_YESNO)

	def cancel(self):
		self.close()

	def up(self):
		self.option = self.option - 1
		if self.option == -1:
			self.option = len(self.optionsList) - 1
		self.startup_option()

	def down(self):
		self.option = self.option + 1
		if self.option == len(self.optionsList):
			self.option = 0
		self.startup_option()

	def startupGB(self):
		self["config"].setText(_("Select Image: %s") %self.list[self.selection])

	def saveGB(self):
		print "[MultiBootStartup] select new startup: ", self.list[self.selection]
		system("cp -f /boot/%s /boot/STARTUP"%self.list[self.selection])
		restartbox = self.session.openWithCallback(self.restartBOX,MessageBox,_("Do you want to reboot now with selected image?"), MessageBox.TYPE_YESNO)

	def left(self):
		self.selection = self.selection - 1
		if self.selection == -1:
			self.selection = len(self.list) - 1
		self.startup()

	def right(self):
		self.selection = self.selection + 1
		if self.selection == len(self.list):
			self.selection = 0
		self.startup()

	def read_startup(self, FILE):
		self.file = FILE
		with open(self.file, 'r') as myfile:
			data=myfile.read().replace('\n', '')
		myfile.close()
		return data

	def list_files(self, PATH):
		files = []
		self.path = PATH
		for name in listdir(self.path):
			if path.isfile(path.join(self.path, name)):
				if SystemInfo["HaveMultiBootHD"]:
					cmdline = self.read_startup("/boot/" + name).split("=",3)[3].split(" ",1)[0]
				if SystemInfo["HaveMultiBootGB"]:
					cmdline = self.read_startup("/boot/" + name).split("=",1)[1].split(" ",1)[0]
				if cmdline in Harddisk.getextdevices("ext4") and not name == "STARTUP":
					files.append(name)
		return files

	def restartBOX(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.close()
