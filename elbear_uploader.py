import serial
import time
import argparse
from sys import exit

ACK = 0x0F                            # МК подтвердил 0b00001111
NACK = 0xF0                           # МК отверг 0b11110000
COMMAND_PACKAGE_SIZE        = b'\x30' # Команда размера пакета 
COMMAND_SEND_PACKAGE        = b'\x60' # Команда отправить пакет 
COMMAND_FULL_ERASE          = b'\xFE'


def cmd_full_erase():
    ser.write(bytes(COMMAND_FULL_ERASE))
    read_byte = ser.read(1) # Прочесть байт ACK/NACK от контроллера
    if int.from_bytes(read_byte, "big") == NACK:
        print("NACK. COMMAND_FULL_ERASE")
        exit()

# Задать размер пакета 
def cmd_package_size(package_size):
    ser.write(COMMAND_PACKAGE_SIZE) # Отправить команду размера передаваемого пакета
    read_byte = ser.read(1) # Прочесть байт ACK/NACK от контроллера
    if int.from_bytes(read_byte, "big") == NACK:
        print("NACK. COMMAND_PACKAGE_SIZE")
        exit()
    ser.write((package_size - 1).to_bytes(1, "big")) # Если контроллер ответил на команду, послать количество передаваемых байт 
    read_byte = ser.read(1) # Прочесть байт ACK/NACK
    if int.from_bytes(read_byte, "big") == NACK:
        print("NACK. COMMAND_PACKAGE_SIZE")
        exit()
    return read_byte == b'\x0f'

# Отправить пакет
def cmd_send_package(data_package):
    # Команда загрузить пакет
    ser.write(COMMAND_SEND_PACKAGE)
    read_byte = ser.read(1) # Прочесть байт ACK/NACK
    if int.from_bytes(read_byte, "big") == NACK:
        print("NACK. COMMAND_SEND_PACKAGE")
        exit()
    # Отправка пакета
    ser.write(bytes(data_package)) # Если контроллер ответил на команду, послать пакет 
    read_byte = ser.read(1) # Прочесть байт ACK/NACK
    if int.from_bytes(read_byte, "big") == NACK:
        print("NACK. SEND_PACKAGE")
        exit()

def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '_', printEnd = "\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    if iteration == total: 
        print()

DEFAULT_BAUDRATE = 230400

def createParser():
    parser = argparse.ArgumentParser(
        prog='bootloader.py',
        description='''Script for writing to external flash on SPIFI interface'''
    )

    parser.add_argument(
        'hexpath',
        default=None,
        nargs='?',
        help='Path to hex file'
    )
    parser.add_argument(
        '--mappath',
        dest='mappath',
        default=None, #'firmware.map',
        help=f"Path to map-file. None by default. If specified, the script filters unused memory from hex."
    )
    parser.add_argument(
        '--no-cache-section-name',
        dest='ncsn',
        default='no-cache',
        help=f"Name of non-cachable memory section in spifi. 'no-cache' by default. If specified, the script filters unused memory from hex."
    )
    parser.add_argument(
        '--com',
        dest='com',
        default=None,
        help=f"COM name. None by default."
    )
    parser.add_argument(
        '--baudrate',
        dest='baudrate',
        default=DEFAULT_BAUDRATE,
        help=f"COM speed. By default: {DEFAULT_BAUDRATE}"
    )

    parser.add_argument(
        '--full-erase',
        dest='fullerase',
        action='store_true',
        default=False
    )
    return parser

parser = createParser()
namespace = parser.parse_args()

REC_TYPE_DATA           = 0
REC_TYPE_EXT_LIN_ADDR   = 4

if namespace.hexpath:
    # читаем хекс
    with open(f"{namespace.hexpath}", "r", encoding='utf-8') as f:
        hex_lines = f.readlines()

    # убираем двоеточие в начале каждой сроки и \n в конце
    for i in range(0, len(hex_lines)):
        hex_lines[i] = hex_lines[i][1:-1]

    # лежат те же данные, что и в lines, но не в виде строки, а в виде интов
    data_lines = []
    for line in hex_lines:
        data = []
        # разбиваем строки по 2 символа - 1 байт
        for i in range(0,len(line), 2):
            data.append(int(line[i:i+2], 16))
        data_lines.append(data)

    # убираем из отправки неиспользуемое место, которое сделал *fill*
    if namespace.mappath and namespace.ncsn:
        with open(f"{namespace.mappath}", "r", encoding='utf-8') as f:
            map_lines = f.readlines()
        
        # находим строку, где впервые упоминается некешируемая область
        for i in range(0, len(map_lines)):
            if namespace.ncsn in map_lines[i]:
                no_cache_line_idx = i
                break
        
        # от нее поднимаемся выше, пока не наткнемся на *fill*
        for i in range(no_cache_line_idx, 0, -1):
            if '*fill*' in map_lines[i]:
                fill_cmd_str = map_lines[i]
                fill_cmd_str = fill_cmd_str.split()
                fill_start_addr = int(fill_cmd_str[1], base=16)
                fill_size       = int(fill_cmd_str[2], base=16)
                # рассчитываем начальный и конечный адреса, которые можно удалить
                filter_start_addr = (fill_start_addr//16 + 1) * 16
                diff = filter_start_addr - fill_start_addr
                filter_stop_addr = filter_start_addr + fill_size - diff - 0x10
                break
        
        # опять пербираем все строки в data_lines и удаляем те, у которых адреса попали между началом и концом филла
        i = 0
        while i < len(data_lines):
            if data_lines[i][3] == REC_TYPE_EXT_LIN_ADDR:
                ext_lin_addr = (data_lines[i][4] << 24) + (data_lines[i][5] << 16)
            if data_lines[i][3] == REC_TYPE_DATA:
                addr = ext_lin_addr + (data_lines[i][1] << 8) + data_lines[i][2]
                if addr >= filter_start_addr and addr <= filter_stop_addr:
                    data_lines.remove(data_lines[i])
                    i -= 1 # текущая строчка удалилась, следующая будет с тем же индексом
            i += 1

    ser = serial.Serial(port = namespace.com, baudrate = namespace.baudrate, timeout = 0.1)

    ping = False
    for i in range(10): # вместо задержки забрасываем запросами
        ping = cmd_package_size(15)
        if ping:
           break

    if ping:
        print("Device connected")
    else:
        print("Device not responding")
        exit()

    if namespace.fullerase:
        print('Erasing memory')
        cmd_full_erase()
        print('Erasing done')
    
    # перебираем все строчки в прочитанном файле и отправляем
    timestart = time.time()
    resolution = 1 # секунды - период выплевывани инфы о прогрессе в терминал
    all_showed = False
    for line in data_lines:
        cmd_package_size(len(line))
        cmd_send_package(bytes(line))

        progress = (data_lines.index(line) + 1) / len(data_lines) * 100
        # printProgressBar(progress, 100, prefix = 'Upload:', suffix = 'Complete', length = 50)
        if time.time() > timestart + resolution:
            timestart += resolution
            print(f'Uploaded {int(progress)}%')
            if progress == 100:
                all_showed = True
            
    if all_showed ==False:
        print(f'Uploaded 100%')
    print("Uploaded successfully.")
else:
    print("Nothing to upload.")

