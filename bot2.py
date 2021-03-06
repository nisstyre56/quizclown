#!/usr/bin/env python
# Quick and dirty IRC triviabot script

testing = False		# test bot *offline* using stdin/stdout debug shell
lurkmode = False	# "lurk" mode - ask questions infrequently

# - based somewhat on example code at http://www.osix.net/modules/article/?id=780
# - based on ircbot.ps by darkf
# - got some help from reading old stackoverflow pages:
#   http://stackoverflow.com/questions/2719017/how-to-set-timeout-on-pythons-socket-recv-method
#   http://stackoverflow.com/questions/613183/python-sort-a-dictionary-by-value

import hints
import heuristic

import sys
import socket
import select
import string
import os
import math
import random
import time
import pickle

# read configuration
conf = open("config.txt", "r")
ircd, port, chan, owner = [conf.readline().strip() for n in xrange(4)]
conf.close()
port = int(port)

# check for custom login script
use_custom_login = True
try:
	lscr = open("login-command.txt", "r")
	login_script = lscr.readline().strip()
	lscr.close()
except IOError:
	use_custom_login = False	

# bot state
READY = 0			# ready to ask a new question
WAIT_ANSWER = 1			# waiting for an answer
QUEST_DELAY = 2			# delay between questions
state = QUEST_DELAY

# setup variables
scores = {owner: 0}		# username -> score dictionary
qid = 0				# current question
quest = []			# question table
ans = []			# answer table
qc = 0				# total question count
question_time = 0		# timestamp of last question asking
hint_timer = 0			# projected timestamp of next hint giving
rs_throttle = time.time()	# reshuffle throttle
info_throttle = time.time()	# !info command throttle

stfu = {owner: 0}		# how many times the bot told a person
				# not to use "quizclown: answer"

skip_stfu = {owner: 0}		# how many times the bot told a person
				# not to vote (!skip) twice

# projected timestamp of next question asking

if testing:
	timeout = time.time()
else:
	timeout = time.time() + 10	# enough time to get connected to the ircd

heur = ""			# accpeted question substring
skips = 0			# skip votes
skippers = []			# skip-voting users

throttle = time.time()		# !hint throttle timer

do_scores = 0			# !scores
auto_scores = time.time() + 100	# periodical automatic scores showing
score_throttle = time.time()	# !scores throttle timer

#########################################################################

# read questions/answers database

count = 0

f = open("questions.txt", "r")
first = True
for line in f:
	if first:
		source = line		# first line is question source text
		first = False
	else:
		# even lines are questions, odd lines answers
		if count % 2 == 0:
			quest.append(line.split("\n")[0])
		else:
			ans.append(line.split("\n")[0])
		count += 1

f.close()
qc = count / 2

# shuffle question meta-indices
qnums = range(qc)
shuffle_sta = random.getstate()
random.shuffle(qnums)

########################################################################


# check for saved game
try:
	sgam = open("sgam.pickle", "r")
	savedat = pickle.load(sgam)
	sgam.close()
	save_shuffle_sta = savedat["shuffle_sta"]
	qid = savedat["qid"]
	scores = savedat["scores"]
	stfu = savedat["stfu"]

	qnums = range(qc)
	random.setstate(save_shuffle_sta)
	random.shuffle(qnums)

	print "saved game loaded"
except IOError:
	print "no saved game found"


if testing:
	print "multiplayer trivia debugging shell"
	print "syntax: username [word [...]]"
	print ""
else:
	s = socket.socket()
	s.connect((ircd, port))
	print "connected"
	s.send("NICK quizclown\r\nUSER quizclown 0 * :trivia quiz bot\r\n")

	# custom identification script ?
	if use_custom_login:
		print "trying to log in..."
		s.send("%s\r\n" % login_script)
		time.sleep(25)
		print "should be logged in now"

	s.send("JOIN "+chan+"\r\n")
	s.setblocking(0)

# procedure to check if an answer is good enough.
def good_enough(quote, ans):
	if quote.upper() == ans.upper() or (quote+"s").upper()==ans.upper() or quote.upper()==(ans+"s").upper():
		return 1
	else:
		return 0

def bot_say(str):
	if testing:
		print str
	else:
		s.send("PRIVMSG "+chan+" :"+str+"\r\n")

bot_say("I'm a triviabot. Type !info for details")

def print_info():
	bot_say("code: https://github.com/bl0ckeduser/quizclown/")
	bot_say("commands: https://raw.github.com/bl0ckeduser/quizclown/master/COMMANDS.txt")
	bot_say("question source: %s" % source)
	if lurkmode:
		bot_say("the bot is in 'lurk' (low question frequency) mode")

while 1:
	if not testing:
		ready = select.select([s], [], [], 1)
	else:
		ready = select.select([sys.stdin], [], [], 1)	
	
	if ready[0]:
		if testing:
			# local debug shell - parse command
			comlin = raw_input()
			if len(comlin.split(" ")) > 1:
				cuser = comlin.split(" ")[0]
				ctext = comlin[comlin.find(" ")+1:]
				line = ":"+cuser+" PRIVMSG "+chan+" :" + ctext + "\r\n"
			else:
				line = ""
		else:
			line = s.recv(1024)

		print "> %s" % line

		words = line.split(" ")

		if words[0]=='PING' and not testing:
			s.send("PONG "+word[1]+"\r\n")


		# hack to allow owner to issue commands in private
		# (useful if e.g. the bot gets kicked)
		if len(words)>2 and words[1]=='PRIVMSG' and words[2]!=chan:
			user = words[0].split(":")[1]
			user = user.split("!")[0]
			if user == owner:
				words[2] = chan

		if len(words)>2 and words[1]=='PRIVMSG' and words[2]==chan:
			# somebody said something in the channel
			quote = ":".join(line.split(":")[2:])
			quote = quote.split("\r\n")[0]
	
			user = words[0].split(":")[1]
			user = user.split("!")[0]
	
			heur = heuristic.heuristic(ans[qnums[qid]])
			full_ans = heuristic.plain_question(ans[qnums[qid]])

			# was it a correct answer ?
			if good_enough(quote, full_ans) or (heur != "" and good_enough(quote, heur)):
				bot_say("%s got it right in %d seconds" % (user, time.time()-question_time))
				
				if user not in scores:
					scores[user] = 0
	
				scores[user] += 1
	
				qid += 1
				state = QUEST_DELAY
				if lurkmode:
					timeout = time.time() + random.randrange(60, 100)			
				else:
					timeout = time.time() + random.randrange(5, 10)
		
			# was it a command ?

			if (quote=="!ask" or quote=="!next") and state==QUEST_DELAY:
				state = READY

			if quote=="!squit":
				if user==owner:
					# save and quit
					sgam = open("sgam.pickle", "w")
					pickle.dump({"shuffle_sta": shuffle_sta, "qid": qid, "scores": scores, "stfu": stfu}, sgam)
					sgam.close()
					bot_say("Game saved; leaving")
					sys.exit(0)
				else:
					bot_say("Only owner can !squit")

			if quote=="!quit":
				if user==owner:
					bot_say("Leaving immediately")
					sys.exit(0)
				else:
					bot_say("Only owner can !quit")

			if quote=="!hint":
				if time.time() >= throttle:
					hint_timer = time.time()
					throttle = time.time() + 3

			if quote=="!scores" or quote=="!score":
				do_scores = 1

			if quote == "!fskip" and user == owner and state == WAIT_ANSWER:
				skips = len(scores) + 1
				if owner in skippers:
					skippers.remove(user)
				quote = "!skip"

			if (quote=="!skip" or quote=="!next") and state==WAIT_ANSWER:
				if user in skippers:
					if user not in skip_stfu:
						skip_stfu[user] = 1
					else:
						skip_stfu[user] += 1
					if skip_stfu[user] == 1:
						bot_say("%s: you can't vote twice!" % user)
					elif skip_stfu[user] == 2:
						bot_say("%s: for the second and last time, you cannot vote twice." % user)
				else:
					skippers.append(user)					
					skips += 1
					if len(scores)/3 - skips == 1:
						bot_say("Need one more vote to skip this question")
					elif len(scores)/3 - skips > 0:
						bot_say("Need %d more votes to skip this question" % (len(scores)/3 - skips))
					if skips >= (len(scores)/3):
						# got enough votes - skip the question
						skips = 0
						skippers = []
						skip_stfu = {owner: 0}
						bot_say("skipping question "+str(qnums[qid]+1)+"")
                                		qid += 1       
	        	                        state = QUEST_DELAY
						if lurkmode:
							timeout = time.time() + random.randrange(60, 200)			
						else:
							timeout = time.time() + random.randrange(5, 10)

			if quote=="!reshuffle" and time.time() >= rs_throttle:
				bot_say("Reshuffling questions ...")
				qnums = range(qc)
				shuffle_sta = random.getstate()
				random.shuffle(qnums)
				qid = 0
				state = READY
				rs_throttle = time.time() + 150

			if quote == "!info" and time.time() >= info_throttle:
				info_throttle = time.time() + 60
				print_info()

			if quote == "!clear":
				if user == owner:
					scores = {owner: 0}
					bot_say("Scores cleared")
				else:
					bot_say("Only owner can !clear")

			if len(quote.split(":")) > 1 and quote.split(":")[0]=="quizclown":
				# the stfu cruft prevents abuse of this

				if user not in stfu:
					stfu[user] = 1
				else:
					stfu[user] += 1

				if stfu[user] == 1:
					bot_say("%s: please just type your answers, without typing my name" % user)
				elif stfu[user] == 2:
					bot_say("%s: for the second time, please do not type my name like that. I ignore these lines." % user)


	if qid >= qc:
		bot_say("This is all for the quiz.")
		max = 0
		key = "nobody"
		for x in scores:
			if scores[x] > max:
				max = scores[x]
				key = x
		if max > 0:
			bot_say("%s has the top score: %d" % (key, max))

		bot_say("cya later ~")

		sys.exit(1)


	if time.time() >= hint_timer and state==WAIT_ANSWER:	
		hint = hints.make_hint(heuristic.plain_question(ans[qnums[qid]]))
		bot_say("Hint: %s" % hint)
		hint_timer = time.time() + 12
		throttle = time.time() + 3

	if time.time() >= score_throttle and do_scores:
		if sum(scores.values()) == 0:
			bot_say("No score yet")
		else:
			n = 0
			scorebuf = "Scores -- "

			for player in sorted(scores, key=scores.get, reverse=True):
				if scores[player] > 1:
					scoreline = "%s: %d pts" % (player, scores[player])
				elif scores[player] > 0:
					scoreline = "%s: %d pt" % (player, scores[player])
				else: continue

				if n > 0:
					scorebuf += ";   "
				scorebuf += scoreline

				# we display three scores per line
				n += 1
				if n % 3 == 0:
					n = 0
					bot_say(scorebuf)
					scorebuf = ""

			# flush scores buffer
			if scorebuf != "":
				bot_say(scorebuf)

		score_throttle = time.time() + 10


	# Clear score request register even if no scores were displayed --
	# it's best to discard throttled requests.
	do_scores = 0
	
	if time.time() >= auto_scores:
		# for the players' convenience, we
		# automatically call the "!score" command
		# every N seconds.
		if lurkmode:
			auto_scores = time.time() + 300
		else:
			auto_scores = time.time() + 200
		do_scores = 1

	# delay between questions
	if state == QUEST_DELAY and time.time() >= timeout:
		state = READY

	# ready to ask a question !
	if state == READY:
		bot_say("%d: %s" % (qnums[qid]+1, quest[qnums[qid]]))
		question_time = time.time()
		hint_timer = time.time() + 8
		state = WAIT_ANSWER

