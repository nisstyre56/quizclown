Quick and dirty IRC trivia bot.

It's my first time writing Python, so my code
will look ugly to more competent programmers.

----------------------------------------------

How to set up quizclown

1. Get some questions and answers into the
   questions.txt file. See questions-spec.txt for
   details on the file format.

   The script import-moxquizz.py will import the 
   moxquizz question database into quizclown (for details, 
   see the comments in import-moxquizz.py).

2. Set up parameters (IRC server, port, channel, bot owner)
   by editing config.txt

3. At the shell, type
         ./bot2.py	(Unix)
   or    bot2.py	(Windows).

   Alternately, you can double-click on bot2.py on
   Windows.

Updating quizclown

   Replace the *.py files in your quizclown directory
   with the latest ones from the quizclown repository,
   keeping your custom config.txt and questions.txt files
   intact.

Custom login scripts

   A 1-line custom login command can be put in
   a file named "login-command.txt". It will be executed
   after connection to the chat server, and the channel
   will only be JOINed after a 20-second delay.

"Lurk" mode

   By setting the lurkmode variable to true in bot2.py,
   "Lurk" mode is activated. In this mode, the bot asks
   questions only once every 1 to 1.5 minute.

Saved games

   If a game is quit using !squit, the game is saved
   into the file sgam.pickle, which is automatically
   checked for when quizclown boots up.



