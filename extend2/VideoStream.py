import cv2
class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
			self.frameNum=0
			self.curFrame=0
			self.frameList=[]
			self.frameList.append(self.file.tell())
			framelength = self.file.read(5) # Get the framelength from the first 5 bits
			while framelength !=b'': 
				# Read the current frame
				framelength=int(framelength)
				data = self.file.read(framelength)
				self.frameList.append(self.file.tell())
				self.frameNum += 1	
				framelength = self.file.read(5)	
		except:
			raise IOError
	def nextFrame(self):
		"""Get next frame."""
		self.file.seek(self.frameList[self.curFrame]) # Get the framelength from the first 5 bits
		data=self.file.read(5)
		if data: 
			framelength = int(data)					
			# Read the current frame
			data = self.file.read(framelength)
			self.curFrame += 1
		return data	
	def frameNbr(self):
		"""Get frame number."""
		return self.curFrame
	def setFrame(self,frame):
		self.curFrame=frame
		if self.curFrame<0: 
			self.curFrame=0	
			
	
	