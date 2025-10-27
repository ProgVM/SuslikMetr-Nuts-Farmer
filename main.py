import asyncio
import os
import re
import random
import json
import sys
from pathlib import Path
from typing import List, Optional

from telethon.sync import TelegramClient
from telethon import errors
from telethon.tl.functions.channels import (
 CreateChannelRequest, 
 DeleteChannelRequest, 
 InviteToChannelRequest,
 EditAdminRequest
)
from telethon.tl.types.chat import ChannelAdminRights 
from telethon.tl.types import InputPeerUser, PeerChannel
# --------------------------------------------------

# --- ГЛОБАЛЬНЫЕ КОНСТАНТЫ ---
# Файл для хранения статистики
STATS_FILE = Path('farm_stats.json') 

class Colors:
  RED = '\033[91m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  BLUE = '\033[94m'
  CYAN = '\033[96m'
  ENDC = '\033[0m'

class ConfigManager:
  def __init__(self):
    self.config_path = Path('config.json')
    self.defaults = {
      'API_ID': os.getenv('API_ID', None),
      'API_HASH': os.getenv('API_HASH', None),
      'RECIPIENT_ID': os.getenv('RECIPIENT_ID', '2113692455'),
      'BOT_ID': 7209725448,
      'MIN_DELAY': 1.0,
      'MAX_DELAY': 3.0
    }
    self.config = self._load_config()

  def _load_config(self):
    if self.config_path.exists():
      try:
        with open(self.config_path, 'r') as f:
          data = json.load(f)
          return {**self.defaults, **data}
      except json.JSONDecodeError:
        print(f"{Colors.YELLOW}Файл config.json поврежден. Используются настройки по умолчанию.{Colors.ENDC}")
        return self.defaults
    return self.defaults

  def _save_config(self):
    with open(self.config_path, 'w') as f:
      json.dump(self.config, f, indent=4)

  def get(self, key):
    return self.config.get(key)

  def set(self, key, value):
    self.config[key] = value
    self._save_config()

class StatsManager:
  def __init__(self):
    self.stats_path = STATS_FILE
    self.stats = self._load_stats()

  def _load_stats(self):
    if self.stats_path.exists():
      try:
        with open(self.stats_path, 'r') as f:
          return json.load(f)
      except json.JSONDecodeError:
        print(f"{Colors.YELLOW}Файл {self.stats_path} поврежден. Начинаем с нуля.{Colors.ENDC}")
        return {}
    return {}

  def _save_stats(self):
    with open(self.stats_path, 'w') as f:
      json.dump(self.stats, f, indent=4)

  def update_stats(self, session_name: str, farmed_nuts: int):
    """Обновляет статистику для сессии и общую статистику"""
    if session_name not in self.stats:
      self.stats[session_name] = {'total_farmed': 0, 'runs': 0}

    self.stats[session_name]['total_farmed'] += farmed_nuts
    self.stats[session_name]['runs'] += 1
    self._save_stats()

  def display_stats(self):
    """Отображает статистику в консоли"""
    total_farmed_all = 0
    print(f"\n{Colors.BLUE}--- СТАТИСТИКА ФАРМИНГА ---{Colors.ENDC}")
    if not self.stats:
      print(f"{Colors.YELLOW}Статистика отсутствует.{Colors.ENDC}")
      return

    for session, data in self.stats.items():
      print(f"[{session}] Нафармлено: {Colors.GREEN}{data['total_farmed']:,}{Colors.ENDC} орешков за {data['runs']} циклов.")
      total_farmed_all += data['total_farmed']

    print("-" * 30)
    print(f"ИТОГО: {Colors.GREEN}{total_farmed_all:,}{Colors.ENDC} орешков.")
    print("--------------------------")

class SessionManager:
 def __init__(self, config: ConfigManager, stats: StatsManager):
  self.config = config
  self.stats = stats
  self.sessions_dir = Path('sessions')
  self.sessions_dir.mkdir(exist_ok=True)
  # API ID/HASH теперь берутся напрямую из ConfigManager при каждом вызове,
  # но мы сохраняем локально для удобства.
  self.api_id = self.config.get('API_ID')
  self.api_hash = self.config.get('API_HASH')

  if not self.api_id or not self.api_hash:
   pass

 def get_sessions(self) -> List[str]:
  return [f.stem for f in self.sessions_dir.glob('*.session')]

 async def add_session(self, phone: str):
  session_name = str(self.sessions_dir / phone.replace('+', '').replace(' ', ''))

  if not self.config.get('API_ID') or not self.config.get('API_HASH'):
   print(f"{Colors.RED}Невозможно добавить сессию: сначала установите API_ID и API_HASH (Опция 5).{Colors.ENDC}")
   return

  # Используем актуальные данные из конфига
  api_id = int(self.config.get('API_ID'))
  api_hash = self.config.get('API_HASH')

  client = TelegramClient(session_name, api_id, api_hash)

  try:
   await client.start(
    phone=phone,
    code_callback=lambda: input(f"{Colors.CYAN}Введите код (должен прийти в Telegram или SMS): {Colors.ENDC}"),
    password=lambda: input(f"{Colors.CYAN}Введите облачный пароль (2FA): {Colors.ENDC}")
   )

   me = await client.get_me()
   if me:
    print(f"{Colors.GREEN}✓ Сессия успешно создана для: {me.first_name} (@{me.username if me.username else 'без username'}){Colors.ENDC}")
   else:
    print(f"{Colors.RED}Ошибка: Не удалось авторизоваться.{Colors.ENDC}")

  except Exception as e:
   print(f"{Colors.RED}Ошибка при создании сессии: {e}{Colors.ENDC}")
  finally:
   await client.disconnect()

 async def start_farm_single_session(self, session_name: str, recipient_id: str):
  SESSION_PATH = self.sessions_dir / session_name
  channel_id = None

  if not SESSION_PATH.with_suffix('.session').exists():
   print(f"{Colors.RED}Сессия {session_name} не найдена.{Colors.ENDC}")
   return

  # Добавляем проверку здесь
  if not self.config.get('API_ID') or not self.config.get('API_HASH'):
   print(f"{Colors.RED}Невозможно запустить фарминг: API_ID или API_HASH не установлены (Опция 5).{Colors.ENDC}")
   return

  # Используем актуальные данные из конфига
  api_id = int(self.config.get('API_ID'))
  api_hash = self.config.get('API_HASH')

  client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
  group_title = f"FarmGroup_{session_name}_{random.randint(1000, 9999)}"

  try:
   await client.start()
   me = await client.get_me()

   print(f"{Colors.GREEN}[{session_name}] Подключен как {me.first_name}. Начинаем фарм-цикл...{Colors.ENDC}")

   # 1. Создание СУПЕРГРУППЫ (Channel)
   print(f"[{session_name}] Создание супергруппы '{group_title}'...")

   result = await client(CreateChannelRequest(
    title=group_title,
    about="Временная группа для фарма",
    megagroup=True 
   ))

   group_entity = result.chats[0]
   channel_id = group_entity.id 

   bot_entity = await client.get_input_entity('suslikmetrbot')

   await client(InviteToChannelRequest(
    channel=group_entity,
    users=[bot_entity]
   ))
   print(f"[{session_name}] Бот добавлен в группу.")

   # ВКЛЮЧАЕМ АНОНИМНОСТЬ ЧЕРЕЗ TL.TYPES
   user_peer = await client.get_input_entity(me.id)

   admin_rights = ChannelAdminRights(
    post_messages=True, 
    add_admins=False,
    change_info=False,
    delete_messages=True,
    ban_users=False,
    invite_users=True,
    pin_messages=False,
    invite_link=False,
    edit_messages=True,
    other=False
   )

   await client(EditAdminRequest(
    channel=group_entity,
    user_id=user_peer,
    admin_rights=admin_rights,
    rank='AnonFarm'
   ))
   print(f"[{session_name}] Установлены права для анонимного постинга (Supergroup).{Colors.ENDC}")

   # 2. Выполнение последовательности команд
   commands = ['/treat', '/iron', '/treat', '/bonus', '/profile']

   for cmd in commands:
    await client.send_message(group_entity, cmd)
    print(f"[{session_name}] Отправлена команда (через Supergroup): {cmd}")
    await asyncio.sleep(random.uniform(self.config.get('MIN_DELAY'), self.config.get('MAX_DELAY')))

   # 3. Обработка ответа на /profile (парсинг орешков)
   messages = await client.get_messages(group_entity, limit=20) 
   profile_message = None

   for msg in messages:
    if msg.sender_id == self.config.get('BOT_ID') and msg.message and 'Профиль' in msg.message:
     profile_message = msg.message
     break

   nuts_balance = 0
   if profile_message:
    match = re.search(r"🌰 Орешков: ([\d,]+)", profile_message)
    if match:
     nuts_balance_str = match.group(1).replace(',', '').strip()
     nuts_balance = int(nuts_balance_str)
     print(f"[{session_name}] Парсинг: Найден баланс орешков: {nuts_balance}")
    else:
     print(f"{Colors.YELLOW}[{session_name}] Не удалось распарсить баланс орешков.{Colors.ENDC}")
   else:
    print(f"{Colors.YELLOW}[{session_name}] Не удалось найти сообщение с профилем.{Colors.ENDC}")

   # 4. Отправка орешков получателю
   if nuts_balance > 0:
    give_command = f"/give {nuts_balance} {recipient_id}"
    await client.send_message(group_entity, give_command)
    print(f"{Colors.CYAN}[{session_name}] Отправлена команда: {give_command} получателю {recipient_id}{Colors.ENDC}")
    self.stats.update_stats(session_name, nuts_balance)
   else:
    print(f"[{session_name}] Баланс нулевой. Орехи не отправлены.")

   # 5. Удаление группы
   await asyncio.sleep(5) 

   await client.delete_dialog(group_entity)
   await client(DeleteChannelRequest(channel=group_entity)) 
   print(f"{Colors.GREEN}[{session_name}] Супергруппа {group_title} успешно удалена. Цикл завершен.{Colors.ENDC}")

  except Exception as e:
   print(f"{Colors.RED}Непредвиденная ошибка при выполнении цикла для {session_name}: {e}{Colors.ENDC}")
  finally:
   if channel_id:
    try:
     entity = await client.get_entity(channel_id)
     await client.delete_dialog(entity)
     await client(DeleteChannelRequest(channel=entity))
    except Exception:
     pass
   await client.disconnect()

 async def start_farm_all_sessions(self):
  # Добавляем проверку здесь, чтобы не допустить вызова TypeError
  if not self.config.get('API_ID') or not self.config.get('API_HASH'):
   print(f"\n{Colors.RED}ОШИБКА: API_ID или API_HASH не установлены. Используйте опцию 5 (Настройки), чтобы ввести их.{Colors.ENDC}")
   return

  sessions = self.get_sessions()
  if not sessions:
   print(f"{Colors.YELLOW}Нет сохраненных сессий для запуска.{Colors.ENDC}")
   return

  tasks = [self.start_farm_single_session(session_name, self.config.get('RECIPIENT_ID')) for session_name in sessions]
  await asyncio.gather(*tasks)
  print(f"{Colors.GREEN}Все фарм-циклы завершены.{Colors.ENDC}")

# --- ФУНКЦИИ МЕНЮ ---

def print_settings_menu(config: ConfigManager):
  """Отображает меню настроек."""
  while True:
    print("\n" + "="*50)
    print(f"{Colors.BLUE}--- НАСТРОЙКИ ---{Colors.ENDC}")
    print(f"1. Установить API_ID (Текущий: {config.get('API_ID')})")
    print(f"2. Установить API_HASH (Текущий: {'***' if config.get('API_HASH') else 'Не установлен'})")
    print(f"3. Установить Получателя Орешков (Текущий: {config.get('RECIPIENT_ID')})")
    print(f"4. Установить Мин. Задержку между командами (Текущая: {config.get('MIN_DELAY')} сек)")
    print(f"5. Установить Макс. Задержку между командами (Текущая: {config.get('MAX_DELAY')} сек)")
    print("0. Назад")

    choice = input(f"\n{Colors.CYAN}Выберите опцию: {Colors.ENDC}").strip()

    if choice == '1':
      new_id = input(f"{Colors.CYAN}Введите новый API_ID: {Colors.ENDC}").strip()
      if new_id.isdigit():
        config.set('API_ID', new_id)
        print(f"{Colors.GREEN}✓ API_ID обновлен.{Colors.ENDC}")
      else:
        print(f"{Colors.RED}Неверный формат ID.{Colors.ENDC}")

    elif choice == '2':
      new_hash = input(f"{Colors.CYAN}Введите новый API_HASH: {Colors.ENDC}").strip()
      config.set('API_HASH', new_hash)
      print(f"{Colors.GREEN}✓ API_HASH обновлен.{Colors.ENDC}")

    elif choice == '3':
      new_recipient = input(f"{Colors.CYAN}Введите ID или Username получателя: {Colors.ENDC}").strip()
      config.set('RECIPIENT_ID', new_recipient)
      print(f"{Colors.GREEN}✓ Получатель обновлен.{Colors.ENDC}")

    elif choice == '4':
      new_delay = input(f"{Colors.CYAN}Введите мин. задержку (секунды): {Colors.ENDC}").strip()
      try:
        delay = float(new_delay)
        if delay < 0: raise ValueError
        config.set('MIN_DELAY', delay)
        print(f"{Colors.GREEN}✓ Мин. задержка обновлена.{Colors.ENDC}")
      except ValueError:
        print(f"{Colors.RED}Неверное значение.{Colors.ENDC}")

    elif choice == '5':
      new_delay = input(f"{Colors.CYAN}Введите макс. задержку (секунды): {Colors.ENDC}").strip()
      try:
        delay = float(new_delay)
        if delay < config.get('MIN_DELAY'): 
          print(f"{Colors.RED}Макс. задержка не может быть меньше мин. задержки ({config.get('MIN_DELAY')}).{Colors.ENDC}")
        else:
          config.set('MAX_DELAY', delay)
          print(f"{Colors.GREEN}✓ Макс. задержка обновлена.{Colors.ENDC}")
      except ValueError:
        print(f"{Colors.RED}Неверное значение.{Colors.ENDC}")

    elif choice == '0':
      return

    else:
      print(f"{Colors.RED}Неверная опция.{Colors.ENDC}")

def main():
  config = ConfigManager()
  stats = StatsManager()
  sm = SessionManager(config, stats)

  while True:
    print("\n" + "="*50)
    print(f"{Colors.BLUE}╔═══════════════════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.BLUE}║{Colors.ENDC} {Colors.GREEN}SuslikMetr Lite - Автофарм Орешков{Colors.ENDC} {Colors.BLUE}║{Colors.ENDC}")
    print(f"{Colors.BLUE}║{Colors.ENDC} {Colors.YELLOW}Telethon Edition v1.41.2{Colors.ENDC} {Colors.BLUE}║{Colors.ENDC}")
    print(f"{Colors.BLUE}╚═══════════════════════════════════════════════════╝{Colors.ENDC}")

    print(f"\n{Colors.GREEN}✓ Получатель орешков: {config.get('RECIPIENT_ID')}{Colors.ENDC}")

    print("\nГЛАВНОЕ МЕНЮ:")
    print("1. Добавить новую сессию")
    print("2. Показать все сессии")
    print("3. Запустить фарм для одной сессии")
    print("4. Запустить фарм для всех сессий")
    print("5. Настройки (API/Задержки/Получатель)")
    print("6. Посмотреть статистику")
    print("0. Выход")

    choice = input(f"\n{Colors.CYAN}Выберите опцию: {Colors.ENDC}").strip()

    if choice == '1':
      phones_input = input(f"{Colors.CYAN}Введите номер(а) телефона через запятую (с +): {Colors.ENDC}")
      phones = [p.strip() for p in phones_input.split(',') if p.strip()]
      for phone in phones:
        if re.match(r'^\+\d+$', phone):
          asyncio.run(sm.add_session(phone))
        else:
          print(f"{Colors.RED}Неверный формат номера: {phone}. Используйте +79XXXXXXXXX.{Colors.ENDC}")

    elif choice == '2':
      sessions = sm.get_sessions()
      print("\nСОХРАНЕННЫЕ СЕССИИ:")
      if sessions:
        for idx, session in enumerate(sessions, 1):
          print(f"{idx}. {session}")
      else:
        print(f"{Colors.YELLOW}Сессий не найдено.{Colors.ENDC}")

    elif choice == '3':
      session_name = input(f"{Colors.CYAN}Введите имя сессии (например, 79001234567): {Colors.ENDC}").strip()
      if session_name in sm.get_sessions():
        asyncio.run(sm.start_farm_single_session(session_name, config.get('RECIPIENT_ID')))
      else:
        print(f"{Colors.RED}Сессия {session_name} не найдена.{Colors.ENDC}")

    elif choice == '4':
      asyncio.run(sm.start_farm_all_sessions())

    elif choice == '5':
      print_settings_menu(config)
      sm = SessionManager(config, stats) 

    elif choice == '6':
      stats.display_stats()

    elif choice == '0':
      print(f"{Colors.BLUE}Выход...{Colors.ENDC}")
      break

    else:
      print(f"{Colors.RED}Неверная опция.{Colors.ENDC}")

if __name__ == '__main__':
  if sys.version_info < (3, 7):
    print("Требуется Python 3.7 или выше.")
    sys.exit(1)

  main()