import asyncio
import os
import re
import random
from pathlib import Path
from typing import List, Optional

# --- ИСПРАВЛЕННЫЕ ИМПОРТЫ ДЛЯ 2.0.0a0 ---
from telethon import Client
from telethon import _tl as tl, errors

SessionPasswordNeededError = errors.SessionPasswordNeededError

# ----------------------------------------

# Цвета для терминала
class Colors:
  HEADER = '\033[95m'
  BLUE = '\033[94m'
  CYAN = '\033[96m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  RED = '\033[91m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'

def clear_screen():
  """Очистка экрана терминала"""
  os.system('cls' if os.name == 'nt' else 'clear')

def print_logo():
  """Вывод логотипа программы"""
  logo = f"""\
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════╗
║ SuslikMetr Lite - Автофарм Орешков ║
║ Telethon Edition v2.0 ║
╚═══════════════════════════════════════════════════╝
{Colors.ENDC}
"""
  print(logo)

class SessionManager:
  def __init__(self):
    self.api_id = os.getenv('API_ID')
    self.api_hash = os.getenv('API_HASH')
    self.sessions_dir = Path('sessions')
    self.sessions_dir.mkdir(exist_ok=True)

    if not self.api_id or not self.api_hash:
      print(f"{Colors.RED}Ошибка: API_ID и API_HASH должны быть установлены в переменных окружения!{Colors.ENDC}")
      exit(1)

  def get_sessions(self) -> List[str]:
    """Получить список всех .session файлов"""
    return [f.stem for f in self.sessions_dir.glob('*.session')]

  async def add_session(self, phone: str):
    """Добавить новую сессию"""
    session_name = f"sessions/{phone.replace('+', '').replace(' ', '')}"

    client = Client(session_name, int(self.api_id), self.api_hash)

    try:
      await client.connect()

      me = await client.get_me()

      if not me:
        # Пытаемся вызвать client.send_code_request, но оборачиваем в try/except
       # на случай, если он отсутствует, чтобы не ломать программу сразу.
        try:
          await client.send_code_request(phone) 
          print(f"{Colors.YELLOW}Код отправлен на номер {phone}{Colors.ENDC}")
        except AttributeError:
          print(f"{Colors.YELLOW}⚠ Внимание: send_code_request отсутствует. Требуется ручной ввод кода.{Colors.ENDC}")
        except Exception as e:
          print(f"{Colors.RED}Ошибка при запросе кода: {e}{Colors.ENDC}")
          return

        code = input(f"{Colors.CYAN}Введите код: {Colors.ENDC}")

        try:
          # --- Используем старый/простой sign_in ---
          me = await client.sign_in(phone, code)
        except SessionPasswordNeededError:
          print(f"{Colors.YELLOW}⚠ Обнаружена двухфакторная аутентификация{Colors.ENDC}")
          password = input(f"{Colors.CYAN}Введите облачный пароль (2FA): {Colors.ENDC}")
          me = await client.sign_in(password=password) 
        except Exception as e:
          print(f"{Colors.RED}Ошибка при входе: {e}{Colors.ENDC}")
          return

      if me:
        print(f"{Colors.GREEN}✓ Сессия успешно создана для: {me.first_name} (@{me.username if me.username else 'без username'}){Colors.ENDC}")
      else:
        print(f"{Colors.RED}Ошибка: Не удалось авторизоваться.{Colors.ENDC}")

    except Exception as e:
      print(f"{Colors.RED}Ошибка при создании сессии: {e}{Colors.ENDC}")
    finally:
      await client.disconnect()


class SuslikFarmer:
  def __init__(self, session_name: str, api_id: str, api_hash: str, recipient: str):
    self.session_path = f"sessions/{session_name}"
    self.api_id = int(api_id)
    self.api_hash = api_hash
    self.recipient = recipient
    self.bot_username = 'suslikmetrbot'
    self.client = Client(self.session_path, self.api_id, self.api_hash)

  async def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
    """Случайная задержка"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

  async def create_group_and_add_bot(self):
    """Создать группу и добавить бота"""
    try:
      # ИСПОЛЬЗУЕМ client.invoke и tl.functions.channels
      result = await self.client.invoke(tl.functions.channels.CreateChannelRequest(
        title=f"Farm_{random.randint(1000, 9999)}",
        about="Temporary farming group",
        megagroup=True
      ))

      channel = result.chats[0]
      print(f"{Colors.GREEN}✓ Создана группа: {channel.title}{Colors.ENDC}")

      # Получаем объект бота
      bot = await self.client.get_entity(self.bot_username)

      # ИСПОЛЬЗУЕМ client.invoke и tl.functions.channels
      await self.client.invoke(tl.functions.channels.InviteToChannelRequest(
        channel=channel,
        users=[bot]
      ))

      print(f"{Colors.GREEN}✓ Бот @{self.bot_username} добавлен в группу{Colors.ENDC}")

      return channel

    except Exception as e:
      print(f"{Colors.RED}Ошибка при создании группы: {e}{Colors.ENDC}")
      return None

  async def send_command_as_channel(self, channel, command: str):
    """Отправить команду от имени канала/группы"""
    try:
      await self.client.send_message(
        entity=self.bot_username,
        message=command,
        from_peer=channel
      )
      print(f"{Colors.CYAN} → Отправлена команда: {command}{Colors.ENDC}")

    except Exception as e:
      print(f"{Colors.RED}Ошибка при отправке команды {command}: {e}{Colors.ENDC}")

  async def get_profile_balance(self, channel) -> Optional[int]:
    """Получить баланс из профиля"""
    try:
      await self.send_command_as_channel(channel, '/profile')
      await asyncio.sleep(2)

      messages = await self.client.get_messages(self.bot_username, limit=5)

      for msg in messages:
        if msg.photo and msg.message:
          # Парсим баланс из caption
          match = re.search(r'🌰 Орешков:\s*([\d,]+)', msg.message)
          if match:
            balance_str = match.group(1).replace(',', '')
            balance = int(balance_str)
            print(f"{Colors.GREEN}✓ Текущий баланс: {balance:,} орешков{Colors.ENDC}")
            return balance

      print(f"{Colors.YELLOW}⚠ Не удалось распарсить баланс{Colors.ENDC}")
      return None

    except Exception as e:
      print(f"{Colors.RED}Ошибка при получении баланса: {e}{Colors.ENDC}")
      return None

  async def send_nuts(self, channel, amount: int):
    """Отправить орешки получателю"""
    try:
      command = f'/give {amount} {self.recipient}'
      await self.send_command_as_channel(channel, command)
      await asyncio.sleep(2)
      print(f"{Colors.GREEN}✓ Отправлено {amount:,} орешков на {self.recipient}{Colors.ENDC}")

    except Exception as e:
      print(f"{Colors.RED}Ошибка при отправке орешков: {e}{Colors.ENDC}")

  async def delete_group(self, channel):
    """Удалить группу"""
    try:
      # ИСПОЛЬЗУЕМ client.invoke и tl.functions.channels.DeleteChannelRequest
      await self.client.invoke(tl.functions.channels.DeleteChannelRequest(channel=channel))
      print(f"{Colors.GREEN}✓ Группа удалена{Colors.ENDC}")

    except Exception as e:
      print(f"{Colors.RED}Ошибка при удалении группы: {e}{Colors.ENDC}")

  async def farm_cycle(self):
    """Один цикл фарма"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*50}{Colors.ENDC}")
    print(f"{Colors.BOLD}Начат цикл фарма для сессии: {self.session_path}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*50}{Colors.ENDC}\n")

    try:
      await self.client.connect()

      # Создаем группу и добавляем бота
      channel = await self.create_group_and_add_bot()
      if not channel:
        return False

      await asyncio.sleep(2)

      # Последовательность команд
      commands = ['/treat', '/iron', '/treat', '/bonus']

      for cmd in commands:
        await self.send_command_as_channel(channel, cmd)
        await self.random_delay(1, 3)

      # Получаем баланс
      balance = await self.get_profile_balance(channel)

      # Если есть баланс, отправляем орешки
      if balance and balance > 0:
        await self.send_nuts(channel, balance)

      # Удаляем группу
      await asyncio.sleep(2)
      await self.delete_group(channel)

      print(f"\n{Colors.GREEN}✓ Цикл фарма завершен успешно!{Colors.ENDC}\n")
      return True

    except Exception as e:
      print(f"{Colors.RED}Ошибка в цикле фарма: {e}{Colors.ENDC}")
      return False
    finally:
      await self.client.disconnect()

  async def start_continuous_farming(self):
    """Запустить непрерывный фарм"""
    cycle_count = 0
    while True:
      cycle_count += 1
      print(f"\n{Colors.YELLOW}{'='*50}")
      print(f"ЦИКЛ #{cycle_count}")
      print(f"{'='*50}{Colors.ENDC}\n")

      success = await self.farm_cycle()

      if success:
        # Задержка между циклами (можно настроить)
        delay = random.randint(60, 120)
        print(f"\n{Colors.YELLOW}⏳ Ожидание {delay} секунд до следующего цикла...{Colors.ENDC}")
        await asyncio.sleep(delay)
      else:
        print(f"\n{Colors.RED}⚠ Ошибка в цикле, ожидание 5 минут...{Colors.ENDC}")
        await asyncio.sleep(300)

def print_menu():
  """Вывод главного меню"""
  print(f"\n{Colors.BOLD}ГЛАВНОЕ МЕНЮ:{Colors.ENDC}")
  print(f"{Colors.CYAN}1.{Colors.ENDC} Добавить новую сессию")
  print(f"{Colors.CYAN}2.{Colors.ENDC} Показать все сессии")
  print(f"{Colors.CYAN}3.{Colors.ENDC} Запустить фарм для одной сессии")
  print(f"{Colors.CYAN}4.{Colors.ENDC} Запустить фарм для всех сессий")
  print(f"{Colors.CYAN}5.{Colors.ENDC} Установить получателя орешков")
  print(f"{Colors.CYAN}0.{Colors.ENDC} Выход")
  print()

async def main():
  manager = SessionManager()
  recipient = os.getenv('RECIPIENT', '')

  while True:
    clear_screen()
    print_logo()

    if recipient:
      print(f"{Colors.GREEN}✓ Получатель орешков: {recipient}{Colors.ENDC}")
    else:
      print(f"{Colors.YELLOW}⚠ Получатель не установлен!{Colors.ENDC}")

    print_menu()

    choice = input(f"{Colors.BOLD}Выберите опцию: {Colors.ENDC}").strip()

    if choice == '1':
      # Добавить сессию
      phones = input(f"\n{Colors.CYAN}Введите номер(а) телефона через запятую (с +): {Colors.ENDC}")
      phone_list = [p.strip() for p in phones.split(',')]

      for phone in phone_list:
        await manager.add_session(phone)
      print()

      input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")

    elif choice == '2':
      # Показать сессии
      sessions = manager.get_sessions()
      print(f"\n{Colors.BOLD}Доступные сессии:{Colors.ENDC}")
      if sessions:
        for i, session in enumerate(sessions, 1):
          print(f"{Colors.CYAN}{i}.{Colors.ENDC} {session}")
      else:
        print(f"{Colors.YELLOW}Нет доступных сессий{Colors.ENDC}")

      input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")

    elif choice == '3':
      # Запустить для одной сессии
      if not recipient:
        print(f"\n{Colors.RED}Сначала установите получателя (опция 5)!{Colors.ENDC}")
        input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")
        continue

      sessions = manager.get_sessions()
      if not sessions:
        print(f"\n{Colors.YELLOW}Нет доступных сессий{Colors.ENDC}")
        input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")
        continue
      print(f"\n{Colors.BOLD}Выберите сессию:{Colors.ENDC}")
      for i, session in enumerate(sessions, 1):
        print(f"{Colors.CYAN}{i}.{Colors.ENDC} {session}")

      try:
        idx = int(input(f"\n{Colors.BOLD}Номер сессии: {Colors.ENDC}")) - 1
        if 0 <= idx < len(sessions):
          farmer = SuslikFarmer(
            sessions[idx],
            manager.api_id,
            manager.api_hash,
            recipient
          )
          await farmer.start_continuous_farming()
      except (ValueError, IndexError):
        print(f"{Colors.RED}Неверный выбор{Colors.ENDC}")
      except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Фарм остановлен пользователем{Colors.ENDC}")

      input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")

    elif choice == '4':
      # Запустить для всех сессий
      if not recipient:
        print(f"\n{Colors.RED}Сначала установите получателя (опция 5)!{Colors.ENDC}")
        input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")
        continue

      sessions = manager.get_sessions()
      if not sessions:
        print(f"{Colors.YELLOW}Нет доступных сессий{Colors.ENDC}")
        input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")
        continue

      print(f"\n{Colors.GREEN}Запуск фарма для {len(sessions)} сессий...{Colors.ENDC}")

      try:
        tasks = []
        for session in sessions:
          farmer = SuslikFarmer(
            session,
            manager.api_id,
            manager.api_hash,
            recipient
          )
          tasks.append(farmer.start_continuous_farming())

        await asyncio.gather(*tasks)
      except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Фарм остановлен пользователем{Colors.ENDC}")

      input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")

    elif choice == '5':
      # Установить получателя
      new_recipient = input(f"\n{Colors.CYAN}Введите username или ID получателя: {Colors.ENDC}").strip()
      if new_recipient:
        recipient = new_recipient
        print(f"{Colors.GREEN}✓ Получатель установлен: {recipient}{Colors.ENDC}")
      else:
        print(f"{Colors.RED}Получатель не может быть пустым{Colors.ENDC}")

      input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")

    elif choice == '0':
      print(f"\n{Colors.GREEN}До свидания!{Colors.ENDC}")
      break

    else:
      print(f"\n{Colors.RED}Неверный выбор!{Colors.ENDC}")
      input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.ENDC}")

if __name__ == '__main__':
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print(f"\n{Colors.YELLOW}Программа завершена пользователем{Colors.ENDC}")