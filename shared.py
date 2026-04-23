import threading

answers_lock = threading.Lock()
answers_store = {}

# إضافة جديدة
sessions_store = {}