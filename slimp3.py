# -*- coding: latin1 -*-
#
# Copyright (C) 2005 Gerome Fournier <jef(at)foutaise.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""SLIMP3 Client protocol implementation in python

This is a python implementation of the SLIMP3 Client protocol. Here goes a
sample usage of this library:

>>> import slimp3
>>> slimp3_client = slimp3.Slimp3Client()
>>> slimp3_client.set_server("localhost")
>>> slimp3_client.set_player("madplay -Q -")
>>> slimp3_client.connect()
>>> slimp3_client.cmd_play()
>>> slimp3_client.cmd_next()
>>> slimp3_client.cmd_stop()
>>> slimp3_client.disconnect()
"""

import os
import sys
import math
import time
import fcntl
import posix
import signal
import popen2
import socket
import select
import struct
import ossaudiodev
import cStringIO

_CLIENT_PORT = 88888
_RECV_BUF_SIZE = 65536

_IR_CODES = {
	'0': 0x76899867,
	'1': 0x7689f00f,
	'2': 0x768908f7,
	'3': 0x76898877,
	'4': 0x768948b7,
	'5': 0x7689c837,
	'6': 0x768928d7,
	'7': 0x7689a857,
	'8': 0x76896897,
	'9': 0x7689e817,
	'DOWN': 0x7689b04f,
	'LEFT': 0x7689906f,
	'RIGHT': 0x7689d02f,
	'UP': 0x7689e01f,
	'VOLDOWN': 0x768900ff,
	'VOLUP': 0x7689807f,
	'POWER': 0x768940bf,
	'REW': 0x7689c03f,
	'PAUSE': 0x768920df,
	'FWD': 0x7689a05f,
	'ADD': 0x7689609f,
	'PLAY': 0x768910ef,
	'SEARCH': 0x768958a7,
	'SHUFFLE': 0x7689d827,
	'REPEAT': 0x768938c7,
	'SLEEP': 0x7689b847,
	'NOW_PLAYING': 0x76897887,
	'SIZE': 0x7689f807,
	'BRIGHTNESS': 0x768904fb
}

def get_mac_addr(ifname):
	"Return the MAC address of interface 'ifname'" 
	SIOCGIFHWADDR = 0x8927 # magic number
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	ifr = ifname + '\0'*(32-len(ifname))
	try:
		r = fcntl.ioctl(s.fileno(), SIOCGIFHWADDR, ifr)
		addr = [ord(i) for i in r[18:24]]
	except IOError:
		addr = [0] * 6
	return addr

class RingBuffer:
	def __init__(self):
		"""Instantiate a SLIMP3's buffer chip

		Instance attributes:

		  self.rptr: read pointer
		  self.wptr: write pointer
		"""
		self._buf = cStringIO.StringIO()
		self._bufsize = 131072
		self.rptr = 0
		self.wptr = 0

	def reset(self):
		"Reset the buffer"
		self.rptr = 0

	def is_empty(self):
		"Check if the buffer is empty"
		return self.wptr == self.rptr

	def read(self, size):
		"Read 'size' bytes from the buffer"
		if self.wptr == self.rptr:
			return ""
		elif self.wptr > self.rptr:
			available_size = self.wptr - self.rptr
		else:
			available_size = self._bufsize - self.rptr
		self._buf.seek(self.rptr)
		data = self._buf.read(min(size, available_size))
		self.rptr += len(data)
		if self.rptr >= self._bufsize:
			self.rptr -= self._bufsize
		return data

	def write(self, wptr, data):
		"Write 'data' to the buffer at position 'wptr'"
		self._buf.seek(wptr)
		self._buf.write(data)
		self.wptr = wptr

class Player:
	def __init__(self, player_cmd):
		"""Instantiate a MPEG decoder
		
		This class is mainly a wrapper around an external MPEG player,
		which will read the MPEG stream from STDIN
		"""
		self._buffer = RingBuffer()
		self._player_cmd = player_cmd
		self._player_process = None

	def start(self):
		"Start the MPEG decoder"
		if not self._player_cmd or self._is_running():
			return
		try:
			self._player_process = popen2.Popen3(self._player_cmd, False, 0)
			self._player_process.fromchild.close()
		except:
			raise

	def stop(self):
		"Stop the MPEG decoder"
		if self._is_running():
			os.kill(self._player_process.pid, signal.SIGTERM)
			self._player_process.wait()
			self._player_process = None
			self._buffer.reset()

	def reset(self):
		"Reset the MPEG decoder"
		self._buffer.reset()

	def fileno(self):
		"Return the input file descriptor of the MPEG decoder"
		if self._is_running():
			return self._player_process.tochild
		else:
			return None

	def feed(self, wptr, data):
		"Feed the MPEG decoder's buffer with 'data'"
		self._buffer.write(wptr, data)

	def has_something_to_eat(self):
		"Is there any data left for the player?"
		return not self._buffer.is_empty()
	
	def eat(self):
		"Let the MPEG decoder eat a few bytes"
		if self._is_running():
			data = self._buffer.read(1400)
			if data:
				self._player_process.tochild.write(data)
				self._player_process.tochild.flush()

	def wptr(self):
		"Return the internal ring buffer write pointer value"
		return self._buffer.wptr

	def rptr(self):
		"Return the internal ring buffer read pointer value"
		return self._buffer.rptr

	def _is_running(self):
		return self._player_process and self._player_process.poll() == -1


class Packet:
	def __init__(self, string):
		"""Instantiate a Slimp3 packet
		
		Instance attributes:

		  self.header: packet header
		  self.data: packet data
		  self.code: slimp3 code inside the header
		"""
		self.header = string[:18]
		self.data = string[18:]
		self.code = string[0]

class Slimp3Client:

	_CTRL_DECODE = 0
	_CTRL_STOP = 1
	_CTRL_STOP_RESET = 3

	def __init__(self):
		"""Instanciate a Slimp3 client
		
		Instance attributes:
		
		  self.lcddata_fd:
		    file descriptor where LCD datas packets can be fetched. The
			first byte gives the length of the following packet.
		"""
		self._starttime = time.time()
		self._pid_child = None
		self._control = None
		self._mac_addr = get_mac_addr("eth0")
		self.set_server("localhost")
		self.set_server_port(3483)
		self._player = None
		self._volume_control = True
		(self.lcddata_fd, self._write_fd) = os.pipe()

	def set_player(self, player_cmd):
		"""Set the player used to play the mpeg stream
		
		The player should read the stream on STDIN
		"""
		self._player = Player(player_cmd)

	def set_server(self, hostname):
		"""Set the Slimp3 server hostname

		Might raise a socket.gaierror exception if the hostname is not valid
		"""
		try:
			self._server_addr = socket.gethostbyname(hostname)
		except socket.gaierror:
			print >>sys.stderr, "Unable to get address of '%s'" % hostname
			raise

	def set_server_port(self, port):
		"""Set the Slimp3 server port
		
		If the value is not valid, a ValueError exception is raised
		"""
		try:
			port = int(port)
			if port < 0 or port > 65535:
				raise ValueError
			self._server_port = port
		except ValueError:
			print >>sys.stderr, "Invalid port number: %s" % port
			raise

	def connect(self):
		"Connect to the Slimp3 server"
		self._create_socket()
		self._pid_child = os.fork()
		if self._pid_child == 0:
			signal.signal(signal.SIGINT, signal.SIG_DFL)
			signal.signal(signal.SIGTERM, self._sigterm_handler)
			self._mainloop()

	def disconnect(self):
		"Disconnect from the Slimp3 server"
		if self._pid_child:
			os.kill(self._pid_child, signal.SIGTERM)
			os.waitpid(self._pid_child, 0)
		self._pid_child = None

	def set_volume_control(self, bool):
		self._volume_control = bool

	for _key in _IR_CODES.keys():
		exec "def cmd_%s(self):\n\
			\"Send the '%s' IR code to the Slimp3 server\"\n\
			self._send_ir(_IR_CODES['%s'])" % (_key.lower(), _key, _key)

	def _sigterm_handler(self, *args):
		self._player.stop()
		signal.signal(signal.SIGTERM, signal.SIG_DFL)
		os.kill(os.getpid(), signal.SIGTERM)

	def _mainloop(self):
		self._send_discovery_request()
		while 1:
			read = [self._socket.fileno()]
			fileno = self._player.fileno()
			if fileno is not None and self._player.has_something_to_eat():
				write = [fileno]
			else:
				write = []
			try:
				(input, output, e) = select.select(read, write, [])
			except select.error:
				print >>sys.stderr, "Select Error!"
				sys.exit(1)
			except:
				raise
			if input:
				self._read_packet()
			elif output and self._control == self._CTRL_DECODE:
				try:
					self._player.eat()
				except IOError:
					print >>sys.stderr, "Backend player died unexpectedly!"
					self.cmd_pause()

	def _create_socket(self):
		self._socket = socket.socket(socket.AF_INET, \
				socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		succeed = False
		for port in range(_CLIENT_PORT, _CLIENT_PORT + 10):
			try:
				self._socket.bind(('', port))
				succeed = True
				break
			except socket.error:
				continue
		if not succeed:
			print >>sys.stderr, "Socket creation error!"
			sys.exit(1)

	def _set_volume(self, level):
		if not self._volume_control:
			return
		if level < 0 or level > 100:
			print >>sys.stderr, "Wrong volume level: %d" % level
			return
		try:
			mixer = ossaudiodev.openmixer()
		except IOError, reason:
			print >>sys.stderr, str(reason)
			return
		if mixer.controls() & (1 << ossaudiodev.SOUND_MIXER_PCM):
			mixer.set(ossaudiodev.SOUND_MIXER_PCM, (level, level))

	def _send_packet(self, packet):
		try:
			sent = self._socket.sendto(packet, 0, (self._server_addr,
				self._server_port))
		except socket.error, reason:
			print >>sys.stderr, reason[1]

	def _send_ack(self, seq):
		wptr = socket.htons(self._player.wptr() >> 1)
		rptr = socket.htons(self._player.rptr() >> 1)
		args = ['c5B3H6B', 'a'] + [0]*5 + [wptr, rptr, seq] + self._mac_addr
		packet = struct.pack(*args)
		self._send_packet(packet);

	def _send_hello(self):
		args = ['c17B', 'h', 1, 0x11] + [0]*9 + self._mac_addr
		packet = struct.pack(*args)
		self._send_packet(packet);

	def _send_discovery_request(self):
		args = ['c17B', 'd', 0, 1, 0x11] + [0]*8 + self._mac_addr
		packet = struct.pack(*args)
		self._send_packet(packet);

	def _send_ir(self, code):
		elapsed = time.time() - self._starttime
		ticks = long(elapsed * 625000) % 2**32
		packet = 'i\x00' + struct.pack('L', socket.htonl(ticks)) + \
			'\xff\x10' + struct.pack('L', socket.htonl(code)) + \
			''.join(["%c" % i for i in self._mac_addr])
		self._send_packet(packet);

	def _read_packet(self):
		try:
			(string, addr) = self._socket.recvfrom(_RECV_BUF_SIZE, 0)
			packet = Packet(string)
			if self._server_addr == '255.255.255.255':
				self._server_addr = addr[0]
			elif addr[0] != self._server_addr:
				print >>sys.stderr, "Got packet from wrong source: %s" % addr[0]
				return
		except:
			print >>sys.stderr, "Unable to receive datas!"
			raise

		if packet.code in ['D', 'h']:
			self._send_hello()
		elif packet.code == 'l':
			self._handle_lcd_packet(packet)
		elif packet.code == 'm':
			self._handle_mpeg_packet(packet)
		elif packet.code == '2':
			self._handle_i2c_packet(packet)
		elif packet.code == 's':
			pass

	def _handle_lcd_packet(self, packet):
		if self._write_fd:
			str = struct.pack("i", len(packet.data))
			os.write(self._write_fd, "%s%s" %(str, packet.data))

	def _handle_mpeg_packet(self, packet):
		(type, control, res1, wptr, res2, seq, res3) = \
			struct.unpack("cB4sH2sH6s", packet.header)
		if control == self._CTRL_DECODE:
			self._player.start()
		elif control == self._CTRL_STOP:
			self._player.stop()
		elif control == self._CTRL_STOP_RESET:
			self._player.stop()
			self._player.reset()
		self._control = control
		self._player.feed(socket.htons(wptr) << 1, packet.data)
		self._send_ack(seq)

	def _handle_i2c_packet(self, packet):
		# handle i2c requests for volume control
		if packet.data[:7] == "\x73\x77\x3A\x77\x68\x77\xB0":
			value = (ord(packet.data[24]) << 16) + (ord(packet.data[18]) << 8) \
					+ ord(packet.data[20])
			level = int(math.sqrt(value/(0x80000+0.0))*100)
			self._set_volume(level)

# vim: ts=4 sw=4 noet
