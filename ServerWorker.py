from random import randint
import sys, traceback, threading, socket
from time import time

from VideoStream import VideoStream
from RtpPacket import RtpPacket

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	DESCRIBE="DESCRIBE"	
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		self.fileName=0
		self.sequenceNum=0
		self.packetSent=0
	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	def processSetupRequest(self,seq,request):
		if self.state == self.INIT:
					# Update state
			print("processing SETUP\n")
					
			try:
				self.clientInfo['videoStream'] = VideoStream(self.fileName)
				self.state = self.READY
			except IOError:
				self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
					
				# Generate a randomized RTSP session ID
			self.clientInfo['session'] = randint(100000, 999999)
					
				# Send RTSP reply
			self.replyRtsp(self.OK_200, seq[1])
			# Get the RTP/UDP port from the last line
			self.clientInfo['rtpPort'] = request[2].split(' ')[3]
	def processPlayRequest(self,seq):
		if self.state == self.READY:
			print("processing PLAY\n")
			self.state = self.PLAYING
				
			# Create a new socket for RTP/UDP
			self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.replyRtsp(self.OK_200, seq[1])
				
			# Create a new thread and start sending RTP packets
			self.clientInfo['event'] = threading.Event()
			self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
			self.clientInfo['worker'].start()					
	def processPauseRequest(self,seq):
		if self.state == self.PLAYING:
			print("processing PAUSE\n")
			self.state = self.READY
				
			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])		
	def processTeardownRequest(self,seq):		
		print("processing TEARDOWN\n")

		if 'event' in self.clientInfo:
			self.clientInfo['event'].set()
			
		self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
		if 'rtpSocket' in self.clientInfo:
			self.clientInfo['rtpSocket'].close()
		print("Packet Sent:"+ str(self.packetSent))
	def processDescribeRequest(self,seq):
		print("Processing describe\n")
		cont = ("v=0\nm=video " + str(self.clientInfo['rtpPort']) + " RTP/AVP 26\na=control:streamid="
			+ str(self.clientInfo['session']) +"\na=mimetype:string;\"video/Mjpeg\"\n"
			+ "Content-Base: " + str(self.clientInfo['videoStream'].filename))
		cont=cont+( "\nContent-Length: " + str(len(cont)) + "\n")
		self.replySdp(self.OK_200,seq[1],cont)
	def processBackwardRequest(self,seq,request):
		print("Processing Backward\n")
		# Create a new socket for RTP/UDP
		self.replyRtsp(self.OK_200, seq[1])
		header,val=request[3].split(' ')
		if self.clientInfo:
			self.clientInfo['videoStream'].setFrame(int(val))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		self.fileName=filename
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			self.processSetupRequest(seq,request)
		# Process PLAY request 		
		elif requestType == self.PLAY:
			if len(request)==4:
				self.processBackwardRequest(seq,request)
			else: 
				self.processPlayRequest(seq)
			
		# Process PAUSE request
		elif requestType == self.PAUSE:
			self.processPauseRequest(seq)
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			self.processTeardownRequest(seq)
		#process describe request
		elif requestType==self.DESCRIBE:
			self.processDescribeRequest(seq)

	def replySdp(self,code,seq,content):
		if code == self.OK_200:
			reply = ('RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session']))
			reply += ("\n" + content)
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")

	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(0.05) 
			
			# Stop sending if request is PAUSE or TEARDOWN
			if self.clientInfo['event'].isSet(): 
				break 
				
			data = self.clientInfo['videoStream'].nextFrame()
			if data:
				try:

					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					self.clientInfo['rtpSocket'].sendto(self.makeRtp(data,self.clientInfo['videoStream'].frameNbr()),(address,port))
					self.packetSent+=1
					self.sequenceNum+=1
				except:
					print("Connection Error")

	def makeRtp(self, payload, frameNbr):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = ('RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session']))
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
