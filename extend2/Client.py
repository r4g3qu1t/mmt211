from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	DESCRIBE=4
	BACKWARD=5
	FORWARD=6
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.workingThread=None
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
		
	def createWidgets(self):
		"""Build GUI."""
		buttonIdx=0
		
		# Create Setup button
		# self.setup = Button(self.master, width=20, padx=3, pady=3)
		# self.setup["text"] = "Setup"
		# self.setup["command"] = self.setupMovie
		# self.setup.grid(row=1, column=buttonIdx, padx=2, pady=2)
		# buttonIdx+=1
		
		# Create backward button
		self.backBut = Button(self.master, width=20, padx=3, pady=3)
		self.backBut["text"] = "backward"
		self.backBut["command"] = self.backward
		self.backBut.grid(row=1, column=buttonIdx, padx=2, pady=2)
		buttonIdx+=1
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=buttonIdx, padx=2, pady=2)
		buttonIdx+=1
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=buttonIdx, padx=2, pady=2)
		buttonIdx+=1

		#create forward button
		self.forBut = Button(self.master, width=20, padx=3, pady=3)
		self.forBut["text"] = "forward"
		self.forBut["command"] = self.forward
		self.forBut.grid(row=1, column=buttonIdx, padx=2, pady=2)
		buttonIdx+=1
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=buttonIdx, padx=2, pady=2)
		buttonIdx+=1
		
		# get description
		self.describe = Button(self.master, width=20, padx=3, pady=3)
		self.describe["text"] = "describe"
		self.describe["command"] =  self.getDescription
		self.describe.grid(row=1, column=buttonIdx, padx=2, pady=2)
		buttonIdx+=1
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 


	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		# if self.state==self.INIT:
		# 	self.setupMovie()
		# 	self.state=self.READY
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			if self.workingThread is  None:
				self.workingThread=threading.Thread(target=self.listenRtp)
				self.workingThread.start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)

	
	def getDescription(self):
		self.sendRtspRequest(self.DESCRIBE)
	def forward(self):
		if self.state==self.READY or self.state==self.PLAYING:
			self.playEvent.clear()
			self.sendRtspRequest(self.FORWARD)
	def backward(self):
		if self.state==self.READY or self.state==self.PLAYING:
			self.playEvent.clear()
			self.sendRtspRequest(self.BACKWARD)

	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					print("Current Seq Num: " + str(currFrameNbr))
										
					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			#tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
			tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			if self.sessionId==0:
				session='\n'
			else: session ="Session "+str(self.sessionId)
			request =	("SETUP " + str(self.fileName) +" RTSP/1.0" "\n" 
						+"CSeq: "+ str(self.rtspSeq) + "\n" 
						+"Transport: RTP/UDP; client_port= " + str(self.rtpPort)+"\n" #from server worker we dont need unicast
						+session)
			self.rtspSocket.send(request.encode())
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.SETUP
			#
			# An example of setup RTPS on wiki:

			#	SETUP rtsp://example.com/media.mp4/streamid=0 RTSP/1.0
      		#	CSeq: 3
      		#	Transport: RTP/AVP;unicast;client_port=8000-8001
			#	Session: 12345678
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = 	("PLAY " + str(self.fileName) +" RTSP/1.0" "\n" 
						+"CSeq: "+ str(self.rtspSeq) + "\n" 
						+"Session: "+str(self.sessionId))
			self.rtspSocket.send(request.encode())
			print(('-'*60 + "\nPLAY request sent to Server...\n" + '-'*60))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PLAY

		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = 	("PAUSE " + str(self.fileName) +" RTSP/1.0" "\n" 
						+"CSeq: "+ str(self.rtspSeq) + "\n" 
						+"Session: "+str(self.sessionId))
			self.rtspSocket.send(request.encode())
			print(( '-'*60 + "\nPAUSE request sent to Server...\n" + '-'*60))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq = self.rtspSeq + 1
			# Write the RTSP request to be sent.
			# request = ...
			request = 	("TEARDOWN " + str(self.fileName) +" RTSP/1.0" "\n" 
						+"CSeq: "+ str(self.rtspSeq) + "\n" 
						+"Session: "+str(self.sessionId))
			self.rtspSocket.send(request.encode())
			print(('-'*60 + "\nTEARDOWN request sent to Server...\n" + '-'*60))
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.TEARDOWN
		#describe request
		elif requestCode==self.DESCRIBE:
			self.rtspSeq = self.rtspSeq + 1
			self.requestSent = self.DESCRIBE
			request = 	("DESCRIBE " + str(self.fileName) + " RTSP/1.0\n"
						+"CSeq: "+str(self.rtspSeq) + "\n"
						+"Sesssion: " + str(self.sessionId))
			self.rtspSocket.send(request.encode("utf-8"))
			print(('-'*60 + "\nDescribe request sent to Server...\n" + '-'*60))
		#backward request
		elif requestCode==self.BACKWARD:
			self.rtspSeq = self.rtspSeq + 1
			self.requestSent=self.BACKWARD
			request = 	("PLAY " + str(self.fileName) +" RTSP/1.0" "\n" 
						+"CSeq: "+ str(self.rtspSeq) + "\n" 
						+"Session: "+str(self.sessionId)+' \n'
						+"range: "+str(self.frameNbr-10))
			self.rtspSocket.send(request.encode())
			print(('-'*60 + "\nBackward request sent to Server...\n" + '-'*60))
			
			print('\nData sent:\n' + request)
		elif requestCode==self.FORWARD:
			self.rtspSeq = self.rtspSeq + 1
			self.requestSent=self.FORWARD
			request = 	("PLAY " + str(self.fileName) +" RTSP/1.0" "\n" 
						+"CSeq: "+ str(self.rtspSeq) + "\n" 
						+"Session: "+str(self.sessionId)+' \n'
						+"range: "+str(self.frameNbr+10))
			self.rtspSocket.send(request.encode())
			print(('-'*60 + "\nBackward request sent to Server...\n" + '-'*60))
			
			print('\nData sent:\n' + request)
		# Send the RTSP request using rtspSocket.
		# ...
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply:
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						#-------------
						# TO COMPLETE
						#-------------
						# Update RTSP state.
						print("Updating RTSP state...")
						# self.state = ...
						self.state = self.READY
						# Open RTP port.
						print("Setting Up RtpPort for Video Stream")
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						# self.state = ...
						if self.state==self.READY:
							self.state = self.PLAYING
							print('-'*60 + "\nClient is PLAYING...\n" + '-'*60)
					elif self.requestSent == self.PAUSE:
						# self.state = ...
						if self.state==self.PLAYING:
							self.state = self.READY
						# The play thread exits. A new thread is created on resume.
							self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						# self.state = ...
						self.state=self.INIT
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
					elif self.requestSent==self.DESCRIBE:
						self.data=data
						print(data)
					elif self.requestSent==self.BACKWARD:
						self.frameNbr-=10
					
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		
		# Set the timeout value of the socket to 0.5sec
		# ...
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #create new socket like init socket
		try:
			# Bind the socket to the address using the RTP port given by the client user
			# ...
			self.rtpSocket.bind((self.serverAddr,self.rtpPort))   # WATCH OUT THE ADDRESS FORMAT!!!!!  rtpPort# should be bigger than 1024
			print("Bind RtpPort Success")
		except:
			#tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)
			tkinter.messagebox.showwarning('Connection Failed', 'Connection to rtpServer failed...')

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		#if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
		if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			#self.playMovie()
			print("Playing Movie")
			threading.Thread(target=self.listenRtp).start()
			#self.playEvent = threading.Event()
			#self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
