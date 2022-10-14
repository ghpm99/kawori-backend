#!/bin/bash
cd /home/opc/kawori-backend/server/uwsgi
export LC_ALL=en_US.UTF8

start (){
/home/opc/kawori-backend/.venv/bin/uwsgi --ini /home/opc/kawori-backend/server/uwsgi/uwsgi.ini;
}

stop () {

/home/opc/kawori-backend/.venv/bin/uwsgi --stop /home/opc/kawori-backend/server/uwsgi/uwsgi.pid;
sleep 5;
}

reload () {

/home/opc/kawori-backend/.venv/bin/uwsgi --reload /home/opc/kawori-backend/server/uwsgi/uwsgi.pid;

}

log () {
    tail -f /home/opc/kawori-backend/server/log/error.log;
}

stats () {
    uwsgitop /home/opc/kawori-backend/server/uwsgi/stats.sock
}

### main logic ###
case "$1" in
  start)
        start
        ;;
  stop)
        stop
        ;;
  restart)
        stop
        start
        ;;
   reload)
        reload
        ;;
      log)
        log
        ;;
      stats)
        stats
        ;;



  *)
        echo $"Opções disponiveis: $0 {start|stop|reload|restart|log|stats}"
        exit 1
esac
exit 0
