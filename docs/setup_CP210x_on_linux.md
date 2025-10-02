<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Як підключити пристрій CP210x на Manjaro Linux

**Короткий висновок**: У більшості випадків драйвер CP210x вже включений у ядро Linux за замовчуванням і не потребує окремої установки. Основні проблеми зазвичай пов'язані з правами доступу до послідовного порту.

## Перевірка драйвера CP210x

CP210x драйвер включений у ядро Linux починаючи з версії 2.6.12 і присутній у Manjaro за замовчуванням. Щоб перевірити, чи завантажений драйвер:[^1_1][^1_2]

```bash
lsmod | grep cp210x
```

Якщо драйвер не відображається, спробуйте завантажити його вручну:

```bash
sudo modprobe cp210x
```


## Перевірка розпізнавання пристрою

Коли ви підключаєте CP210x пристрій, перевірте, чи система його розпізнає:

```bash
# Перевірте підключені USB пристрої
lsusb

# Перевірте системні повідомлення
dmesg | grep -i cp210

# Або більш загальний пошук
dmesg | tail -20
```

Успішне підключення має показати повідомлення на кшталт:[^1_3]

- "CP210x converter detected"
- "CP210x converter now attached to ttyUSB0"


## Основна проблема: права доступу

Найчастіша проблема з CP210x пристроями на Linux - це права доступу до `/dev/ttyUSB0`.[^1_4][^1_5]

### Перевірка поточних прав

```bash
ls -l /dev/ttyUSB*
```

Зазвичай виводиться щось на кшталт:

```
crw-rw---- 1 root dialout 188, 0 дата /dev/ttyUSB0
```


### Вирішення проблем з правами

**Метод 1: Додавання користувача до групи dialout**

```bash
# Додати поточного користувача до групи dialout
sudo usermod -a -G dialout $USER

# Перевірити членство в групах
groups

# Вийти з системи і увійти знову для застосування змін
```

**Метод 2: Додавання до групи uucp (альтернатива)**

На деяких системах Manjaro може використовуватися група `uucp` замість `dialout`:

```bash
sudo usermod -a -G uucp $USER
```


## Тестування підключення

Після налаштування прав доступу протестуйте пристрій:

```bash
# Простий тест читання (буде виводити дані з пристрою)
cat /dev/ttyUSB0

# Або використовуйте screen для інтерактивного тестування
screen /dev/ttyUSB0 9600

# Альтернативно - minicom
sudo pacman -S minicom
minicom -D /dev/ttyUSB0
```


## Налаштування udev правил (додаткове)

Для постійного налаштування прав доступу можна створити udev правило:[^1_6]

```bash
sudo nano /etc/udev/rules.d/50-cp210x.rules
```

Додайте:

```
# CP210x USB to Serial
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", GROUP="dialout"
```

Або для конкретного пристрою:

```
KERNEL=="ttyUSB0", MODE="0666"
```

Після створення правила перезавантажте udev:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```


## Усунення несправностей

**Якщо пристрій не розпізнається:**

1. Перевірте vendor ID та product ID:

```bash
lsusb
```

2. Переконайтеся, що ID присутні у драйвері:

```bash
modinfo cp210x | grep alias
```

3. Якщо ваш пристрій має нестандартні ID, можливо доведеться додати їх до драйвера.[^1_3]

**Налагодження з детальним виводом:**

```bash
sudo rmmod cp210x
sudo modprobe cp210x debug=1
dmesg | tail -20
```

**Перевірка конфліктів з іншими драйверами:**

Іноді драйвер `brltty` може конфліктувати з CP210x пристроями:[^1_5]

```bash
sudo systemctl stop brltty
sudo systemctl disable brltty
```


## Специфічні застосування

Для роботи з мікроконтролерами (Arduino, ESP32) через Arduino IDE чи PlatformIO переконайтеся, що:

1. Користувач доданий до потрібної групи
2. IDE запущена з правильними правами
3. Вибрано правильний порт (/dev/ttyUSB0)

Таким чином, у більшості випадків CP210x пристрої працюють "з коробки" на Manjaro Linux - потрібно лише правильно налаштувати права доступу.
<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_30][^1_31][^1_32][^1_33][^1_34][^1_35][^1_36][^1_37][^1_38][^1_39][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://forum.manjaro.org/t/arduinoide-how-to-install-esp32-driver-for-usb-to-serial-communication/132777

[^1_2]: https://stackoverflow.com/questions/42180390/how-to-download-and-install-drivers-for-cp210x-usb-to-uart-bridge-on-ubuntu

[^1_3]: http://www.etheus.net/CP210x_Linux_Driver

[^1_4]: https://github.com/esp8266/source-code-examples/issues/26

[^1_5]: https://forum.manjaro.org/t/make-ttyusb0-permanently-writable-for-arduino-development/97464

[^1_6]: https://bbs.archlinux.org/viewtopic.php?id=86088

[^1_7]: https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers

[^1_8]: https://voltiq.ru/downloads/INTEGRATING-CP210X-DRIVER.pdf

[^1_9]: https://www.silabs.com/documents/public/application-notes/an809-integrating-cp210x-vcom-port-driver.pdf

[^1_10]: https://linux-hardware.org/?id=usb%3A10c4-ea60\&page=2

[^1_11]: https://github.com/k0rnh0li0/cp210x-arch

[^1_12]: https://community.silabs.com/s/question/0D5Vm00000PqYAnKAN/cp210x-linux-ubuntu-driver?language=ja

[^1_13]: https://community.silabs.com/s/article/configuring-the-cp210x-on-linux

[^1_14]: https://forum.manjaro.org/t/how-to-add-cp210x-driver-to-linux-pinephone/105418/4

[^1_15]: https://forums.developer.nvidia.com/t/installing-cp210x-usb-to-uart-driver-on-jetson-nano/78886

[^1_16]: https://bbs.archlinux.org/viewtopic.php?id=182033

[^1_17]: https://www.scribd.com/document/490163185/CP210x-Setup-Guide-1-2-0

[^1_18]: https://forum.manjaro.org/t/how-to-add-cp210x-driver-to-linux-pinephone/105418

[^1_19]: https://docs.elephantrobotics.com/docs/myagv_jn23_en/5-BasicApplication/5.2-ApplicationUse/5.2.2-mystudio/jetsonnano/2-install_driver.html

[^1_20]: https://bbs.archlinux.org/viewtopic.php?id=270239

[^1_21]: https://www.reddit.com/r/linuxquestions/comments/18zb1k6/missing_cp120x_on_arch/

[^1_22]: https://robostart.ru/iguana/drivers/

[^1_23]: https://forum.khadas.com/t/ch340-and-cp210x-support/16721

[^1_24]: https://www.cyberciti.biz/faq/linux-show-the-status-of-modules-driver-lsmod-command/

[^1_25]: https://stackoverflow.com/questions/24003848/cp210-driver-installation-on-linux

[^1_26]: https://community.silabs.com/s/question/0D51M00007xeFnASAU/cp210x-linux-driver-unable-to-enable-uart?language=zh_TW

[^1_27]: https://community.silabs.com/s/question/0D5Vm00000PqYAnKAN/cp210x-linux-ubuntu-driver?language=en_US

[^1_28]: https://community.silabs.com/s/question/0D51M00007xeNF7SAM/cp210x-wont-work-on-dell-laptop-ubuntu-1804?language=en_US

[^1_29]: https://community.silabs.com/s/article/how-to-check-if-the-cp210x-be-enumerated-successfully-on-linux

[^1_30]: https://forum.manjaro.org/t/udev-rule-with-user-rights/140595

[^1_31]: https://bbs.archlinux.org/viewtopic.php?id=302209

[^1_32]: https://forums.developer.nvidia.com/t/jetson-tk1-r21-1-and-siliconlab-cp210x-driver/40069

[^1_33]: https://forum.arduino.cc/t/permission-denied-on-dev-ttyacm0/475568

[^1_34]: https://community.silabs.com/s/article/cp210xmanufacturing-library-in-linux

[^1_35]: https://hyperion-project.org/forum/index.php?thread%2F12817-i-can-t-connect-to-my-arduino-on-manjaro-linux-using-hyperion-ng-snap%2F

[^1_36]: https://www.helifreak.com/showthread.php?t=808683

[^1_37]: https://esp32.com/viewtopic.php?t=10379

[^1_38]: https://github.com/Klipper3d/klipper/issues/835?timeline_page=1

[^1_39]: https://android.googlesource.com/kernel/common/+/35556bed836f/drivers/usb/serial/cp210x.c


---

# Як додати новий alias для ID 840e в CP210x драйвер

**Короткий висновок**: Для додавання нового Product ID (840e) до CP210x драйвера використовуйте команду `echo` для запису vendor та product ID до файлу `/sys/bus/usb-serial/drivers/cp210x/new_id`. Це динамічно додасть підтримку вашого пристрою без перекомпіляції ядра.

## Метод 1: Динамічне додавання ID (рекомендований)

### Основна команда

Для додавання Product ID `840e` до CP210x драйвера виконайте наступні команди:[^2_1][^2_2]

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

Для автоматичного додавання ID при підключенні пристрою створіть udev правило:[^2_3]

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

Якщо отримуєте помилку "Permission denied" навіть з sudo, використовуйте:[^2_1]

```bash
# Правильний синтаксис з sh -c
sudo sh -c 'echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id'

# Або відкрийте shell з правами root
sudo -s
echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id
exit
```


## Альтернативний метод через modprobe параметри

Також можна завантажити модуль з параметрами при старті:[^2_4]

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
<span style="display:none">[^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_16][^2_17][^2_18][^2_19][^2_20][^2_21][^2_22][^2_23][^2_24][^2_25][^2_26][^2_27][^2_28][^2_29][^2_30][^2_31][^2_32][^2_33][^2_5][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: https://stackoverflow.com/questions/38330155/updating-product-vendor-id-on-raspberry-pi-cp210x

[^2_2]: https://www.reddit.com/r/linuxquestions/comments/1m9bf40/need_to_specify_usbserial_driver_to_load/

[^2_3]: https://blog.ewelt.net/posts/linux/dps5315-characterdevice/

[^2_4]: https://www.sealevel.com/how-to-configure-usb-serial-adapters-in-linux

[^2_5]: https://ftdichip.com/faq/how-do-i-add-a-custom-pid-to-the-ftdi_sio-linux-com-port-driver/

[^2_6]: https://blog.manzelseet.com/fixing-cp2102-with-custom-vidpid.html

[^2_7]: https://stackoverflow.com/questions/442833/how-to-force-driver-to-device-match-in-linux

[^2_8]: https://forums.developer.nvidia.com/t/installing-cp210x-usb-to-uart-driver-on-jetson-nano/78886

[^2_9]: https://forums.developer.nvidia.com/t/problems-communicating-via-usb-to-serial-cp210x/44758

[^2_10]: https://www.linux.org.ru/forum/general/12031687

[^2_11]: https://community.silabs.com/s/question/0D58Y000097WuavSAC/cp210x-driver-wont-install?language=ru

[^2_12]: https://krinkinmu.github.io/2020/08/02/ftdi.html

[^2_13]: https://community.silabs.com/s/article/customizing-cp210x-drivers-to-recognize-new-vid-pid

[^2_14]: https://forums.balena.io/t/update-to-the-cp210x-usb-driver-on-balenaos/5603

[^2_15]: https://ez.analog.com/linux-software-drivers/f/q-a/103258/enable-usb-serial-converter-driver

[^2_16]: https://community.silabs.com/s/question/0D51M00007xeQ6VSAU/linux-add-vidpid-for-customer-device?language=ko

[^2_17]: https://community.openhab.org/t/qivicon-usb-zigbee-and-hm-mod-rpi-pcb-on-one-pi/48156/11

[^2_18]: https://bbs.archlinux.org/viewtopic.php?id=144404

[^2_19]: https://www.linuxjournal.com/article/6434

[^2_20]: https://community.platformio.org/t/cp210x-driver-does-not-work-with-esp32-on-windows-10/13863

[^2_21]: https://learn.microsoft.com/en-us/answers/questions/4203255/usb-driver-from-silicon-labs-cp210x-will-not-insta

[^2_22]: https://silicon-laboratories.drivers-download.net/other/silicon-labs-cp210x-usb-to-uart-bridge/windows-7-x64

[^2_23]: https://bbs.archlinux.org/viewtopic.php?id=182033

[^2_24]: https://support.wirenboard.com/t/cp210x-ko-yadernyj-modul/614

[^2_25]: https://community.silabs.com/s/question/0D58Y0000AHKZ7jSQH/cp210x-driver?language=ru

[^2_26]: https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers

[^2_27]: https://community.silabs.com/s/question/0D58Y00008K88dCSAR/how-to-download-cp210x-usb-to-uart-bridge-vcp-drivers?language=ru

[^2_28]: https://community.silabs.com/s/question/0D5Vm00000PqYAnKAN/cp210x-linux-ubuntu-driver?language=en_US

[^2_29]: https://forums.developer.nvidia.com/t/solved-unable-to-install-cp210x-drivers-for-usb-serial-communication-on-tx2-with-orbitty/64282

[^2_30]: https://community.silabs.com/s/article/cp210x-virtual-com-port-drivers

[^2_31]: https://forum.manjaro.org/t/how-to-add-cp210x-driver-to-linux-pinephone/105418

[^2_32]: https://community.silabs.com/s/question/0D5Vm00000PqYAnKAN/cp210x-linux-ubuntu-driver?language=es

[^2_33]: https://www.youtube.com/watch?v=WdRg_yYd00U

