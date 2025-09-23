<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Як додати новий alias для ID 840e в CP210x драйвер

**Короткий висновок**: Для додавання нового Product ID (840e) до CP210x драйвера використовуйте команду `echo` для запису vendor та product ID до файлу `/sys/bus/usb-serial/drivers/cp210x/new_id`. Це динамічно додасть підтримку вашого пристрою без перекомпіляції ядра.

## Метод 1: Динамічне додавання ID (рекомендований)

### Основна команда

Для додавання Product ID `840e` до CP210x драйвера виконайте наступні команди:[^1][^2]

```bash
# Завантажте модуль cp210x (якщо не завантажений)
sudo modprobe cp210x

# Додайте новий vendor/product ID
sudo sh -c 'echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id'
```

**Пояснення параметрів:**

- `10c4` - стандартний Vendor ID Silicon Labs
- `840e` - ваш Product ID


### Перевірка результату

Після виконання команд підключіть пристрій та перевірте:

```bash
# Перевірте системні повідомлення
dmesg | tail -10

# Шукайте повідомлення типу:
# "cp210x converter detected"
# "cp210x converter now attached to ttyUSB0"

# Перевірте створення послідовного порту
ls -l /dev/ttyUSB*
```


## Метод 2: Постійне налаштування через udev правила

Для автоматичного додавання ID при підключенні пристрою створіть udev правило:[^3]

### Створення udev правила

```bash
sudo nano /etc/udev/rules.d/99-cp210x-840e.rules
```

Додайте наступний вміст:

```
# Автоматичне додавання CP210x ID 840e
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="10c4", ATTR{idProduct}=="840e", RUN+="/bin/sh -c 'echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id'"
```


### Завантаження модуля при старті

Створіть файл для автоматичного завантаження модуля:

```bash
sudo nano /etc/modules-load.d/cp210x.conf
```

Додайте:

```
cp210x
```


### Застосування змін

```bash
# Перезавантажте udev правила
sudo udevadm control --reload-rules
sudo udevadm trigger

# Або перезавантажте систему
sudo reboot
```


## Метод 3: Перевірка перед додаванням

### Визначення поточних підтримуваних ID

```bash
# Перевірте поточні aliases модуля
modinfo cp210x | grep alias

# Або подивіться підтримувані ID у коді ядра
cat /lib/modules/$(uname -r)/modules.alias | grep cp210x
```


### Перевірка вашого пристрою

```bash
# Підключіть пристрій та перевірте його ID
lsusb | grep 10c4

# Мала б з'явитися строка на кшталт:
# Bus XXX Device XXX: ID 10c4:840e Silicon Labs ...
```


## Усунення несправностей

### Якщо команда не спрацьовує

1. **Перевірте існування шляху:**

```bash
ls -l /sys/bus/usb-serial/drivers/cp210x/
```

2. **Перезавантажте модуль:**

```bash
sudo rmmod cp210x
sudo modprobe cp210x
```

3. **Перевірте права доступу:**

```bash
# Переконайтеся, що команда виконується з правами root
sudo -i
echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id
exit
```


### Помилки при записі

Якщо отримуєте помилку "Permission denied" навіть з sudo, використовуйте:[^1]

```bash
# Правильний синтаксис з sh -c
sudo sh -c 'echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id'

# Або відкрийте shell з правами root
sudo -s
echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id
exit
```


## Альтернативний метод через modprobe параметри

Також можна завантажити модуль з параметрами при старті:[^4]

```bash
sudo modprobe cp210x vendor=0x10c4 product=0x840e
```

Але цей метод працює тільки для одного додаткового ID.

## Важливі зауваження

1. **Тимчасовість**: Додавання через `new_id` діє до перезавантаження системи
2. **Постійність**: Для постійної дії використовуйте udev правила
3. **Конфлікти**: Переконайтеся, що інший драйвер не захоплює ваш пристрій
4. **Vendor ID**: Використовуйте правильний vendor ID (10c4 для Silicon Labs)

Після виконання цих кроків ваш пристрій з ID `10c4:840e` має розпізнаватися CP210x драйвером і створювати послідовний порт `/dev/ttyUSB0` (або наступний доступний номер).
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30][^31][^32][^33][^5][^6][^7][^8][^9]</span>

<div style="text-align: center">⁂</div>

[^1]: https://stackoverflow.com/questions/38330155/updating-product-vendor-id-on-raspberry-pi-cp210x

[^2]: https://www.reddit.com/r/linuxquestions/comments/1m9bf40/need_to_specify_usbserial_driver_to_load/

[^3]: https://blog.ewelt.net/posts/linux/dps5315-characterdevice/

[^4]: https://www.sealevel.com/how-to-configure-usb-serial-adapters-in-linux

[^5]: https://ftdichip.com/faq/how-do-i-add-a-custom-pid-to-the-ftdi_sio-linux-com-port-driver/

[^6]: https://blog.manzelseet.com/fixing-cp2102-with-custom-vidpid.html

[^7]: https://stackoverflow.com/questions/442833/how-to-force-driver-to-device-match-in-linux

[^8]: https://forums.developer.nvidia.com/t/installing-cp210x-usb-to-uart-driver-on-jetson-nano/78886

[^9]: https://forums.developer.nvidia.com/t/problems-communicating-via-usb-to-serial-cp210x/44758

[^10]: https://www.linux.org.ru/forum/general/12031687

[^11]: https://community.silabs.com/s/question/0D58Y000097WuavSAC/cp210x-driver-wont-install?language=ru

[^12]: https://krinkinmu.github.io/2020/08/02/ftdi.html

[^13]: https://community.silabs.com/s/article/customizing-cp210x-drivers-to-recognize-new-vid-pid

[^14]: https://forums.balena.io/t/update-to-the-cp210x-usb-driver-on-balenaos/5603

[^15]: https://ez.analog.com/linux-software-drivers/f/q-a/103258/enable-usb-serial-converter-driver

[^16]: https://community.silabs.com/s/question/0D51M00007xeQ6VSAU/linux-add-vidpid-for-customer-device?language=ko

[^17]: https://community.openhab.org/t/qivicon-usb-zigbee-and-hm-mod-rpi-pcb-on-one-pi/48156/11

[^18]: https://bbs.archlinux.org/viewtopic.php?id=144404

[^19]: https://www.linuxjournal.com/article/6434

[^20]: https://community.platformio.org/t/cp210x-driver-does-not-work-with-esp32-on-windows-10/13863

[^21]: https://learn.microsoft.com/en-us/answers/questions/4203255/usb-driver-from-silicon-labs-cp210x-will-not-insta

[^22]: https://silicon-laboratories.drivers-download.net/other/silicon-labs-cp210x-usb-to-uart-bridge/windows-7-x64

[^23]: https://bbs.archlinux.org/viewtopic.php?id=182033

[^24]: https://support.wirenboard.com/t/cp210x-ko-yadernyj-modul/614

[^25]: https://community.silabs.com/s/question/0D58Y0000AHKZ7jSQH/cp210x-driver?language=ru

[^26]: https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers

[^27]: https://community.silabs.com/s/question/0D58Y00008K88dCSAR/how-to-download-cp210x-usb-to-uart-bridge-vcp-drivers?language=ru

[^28]: https://community.silabs.com/s/question/0D5Vm00000PqYAnKAN/cp210x-linux-ubuntu-driver?language=en_US

[^29]: https://forums.developer.nvidia.com/t/solved-unable-to-install-cp210x-drivers-for-usb-serial-communication-on-tx2-with-orbitty/64282

[^30]: https://community.silabs.com/s/article/cp210x-virtual-com-port-drivers

[^31]: https://forum.manjaro.org/t/how-to-add-cp210x-driver-to-linux-pinephone/105418

[^32]: https://community.silabs.com/s/question/0D5Vm00000PqYAnKAN/cp210x-linux-ubuntu-driver?language=es

[^33]: https://www.youtube.com/watch?v=WdRg_yYd00U

