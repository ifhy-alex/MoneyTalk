import logging
import os

from moneytalk.desktop.app import main

code = main()
# Todo quedó apagado: salir ya, sin esperar a que el runtime de la ventana (.NET) termine
# por su cuenta, que puede tardar varios segundos y mantiene tomado el candado de instancia.
logging.shutdown()
os._exit(code)
