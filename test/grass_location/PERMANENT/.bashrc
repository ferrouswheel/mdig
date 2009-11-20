test -r ~/.alias && . ~/.alias
PS1='GRASS 6.5.svn (grass_location):\w > '
PROMPT_COMMAND="'/usr/local/grass-6.5.svn/etc/prompt.sh'"
export PATH="/usr/local/grass-6.5.svn/bin:/usr/local/grass-6.5.svn/scripts:/home/joel/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games"
export HOME="/home/joel"
export GRASS_SHELL_PID=$$
trap "echo \"GUI issued an exit\"; exit" SIGINT
