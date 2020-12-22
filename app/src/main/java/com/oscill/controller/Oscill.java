package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.obex.ClientSession;
import com.oscill.obex.Header;
import com.oscill.types.BitSet;
import com.oscill.utils.Log;

import java.io.IOException;

public class Oscill extends BaseOscillController {

    private static final String TAG = Log.getTag(Oscill.class);

    public Oscill(@NonNull ClientSession clientSession) {
        super(clientSession);
    }

    public void reset() throws IOException {
        getClientSession().reset();
    }

    public int connect() throws IOException {
        return getClientSession().connect(null).getResponseCode();
    }

    public int disconnect() throws IOException {
        return getClientSession().disconnect(null).getResponseCode();
    }

    @NonNull
    public String getDeviceId() throws IOException {
        return bytesToString(getProperty("VNM", Header.OSCILL_4BYTE));
    }

    @NonNull
    public String getDeviceSerialNumber() throws IOException {
        return bytesToString(getProperty("VSN", Header.OSCILL_4BYTE));
    }

    @NonNull
    public String getDeviceHardwareVersion() throws IOException {
        return bytesToString(getProperty("VHW", Header.OSCILL_4BYTE));
    }

    @NonNull
    public String getDeviceSoftwareVersion() throws IOException {
        return bytesToString(getProperty("VSW", Header.OSCILL_4BYTE));
    }

    /**
     * Имя свойства: MCd - Длительность машинного цикла по умолчанию
     * Формат свойства: 2 байта, беззнаковое
     * Описание свойства: длительность машинного цикла процессора, гарантированно обеспечивающая егостабильную работу
     * Единица измерения: по 10 пс
     * Пример свойства (базовая модель Oscill): MCd=0x07D0 (50МГц тактовая частота)
     */
    public int getCPUTickDefLength() throws IOException {
        return bytesToInt(getProperty("MCd", Header.OSCILL_2BYTE));
    }

    /**
     * Имя свойства: MCl - Минимальная длительность машинного цикла
     * Формат свойства: 2 байта, беззнаковое
     * Описание свойства: минимальная длительность машинного цикла процессора
     * (типовая способность к увеличению тактовой частоты свыше номинальной, “разгон”)
     * Единица измерения: по 10 пс
     * Пример свойства (базовая модель Oscill): MCl=0x03E8 (100МГц тактовая частота)
     */
    public int getCPUTickMinLength() throws IOException {
        return bytesToInt(getProperty("MCl", Header.OSCILL_2BYTE));
    }

    /**
     * Имя регистра: MC - Длительность машинного цикла
     * Формат регистра: 2 байта, беззнаковый
     * Описание регистра: Длительность машинного цикла контроллера.
     * Единица измерения: по 10 пс, то есть максимальная длительность – 655нс, что соответствует минимальной тактовой частоте  ~1,5МГц.
     * От регистра зависят: нет.
     * Регистр зависит от: нет.
     */
    public int setCPUTickLength(int value) throws IOException {
        Log.i(TAG, "setCPUTickLength: ", value);
        return bytesToInt(setRegistry("MC", Header.OSCILL_2BYTE, intTo2Bytes(value)));
    }

    public int getCPUTickLength() throws IOException {
        return bytesToInt(getRegistry("MC", Header.OSCILL_2BYTE));
    }

    /**
     * Имя свойства: TOl - Минимальный период однократной дискретизации (realtime)
     * Описание свойства:  количество машинных циклов на одну выборку, начиная с которого осцилл допускает
     * произвольное значение регистра TS. Оцифровка быстрее TOl возможна только с такими значениями регистра TS,
     * какие указаны в свойстве TOv
     * Формат свойства:  2 байта
     * Единица измерения: машинные циклы, умноженные на 256.
     * Свойство зависит от: нет.
     * Пример свойства (базовая модель Oscill): TOl =0x2000
     */
    public int getSamplingMinPeriod() throws IOException {
        return bytesToInt(getProperty("TOl", Header.OSCILL_2BYTE));
    }

    /**
     * Имя регистра: TS - Период дискретизации
     * Формат регистра: 4 байта, беззнаковый
     * Описание регистра: Интервал между выборками в возвращаемом массиве
     * Единица измерения: машинные циклы, умноженные на 256.
     * Максимальный период дискретизации при машинном цикле=10нс равен 167мс, что обеспечивает 5,4 сек/дел при 32х выборках / деление.
     * Минимальное значение: в зависимости от способа оцифровки – TOl, TMl, TPl
     * Регистр зависит от:  нет (наивысший приоритет).
     * От регистра зависят: способ оцифровки RS, обработка канала M1, задержка развертки TD.
     */
    public int setSamplingPeriod(int value) throws IOException {
        Log.i(TAG, "setSamplingPeriod: ", value);
        return bytesToInt(setRegistry("TS", Header.OSCILL_4BYTE, intTo4Bytes(value)));
    }

    public int getSamplingPeriod() throws IOException {
        return bytesToInt(getRegistry("TS", Header.OSCILL_4BYTE));
    }

    /**
     * Имя регистра: RS - Способ оцифровки
     * Формат регистра: 1 байт, побитный
     * Описание регистра: 	бит 0:		0	- однократная (realtime)
     *  					            1 	- стробоскопическая (эквивалентная, RIS)
     * 			            бит 1:		0 	- передача после оцифровки
     *                                  1  	- параллельная (realtime) передача
     *                      бит 2:		0 	- буферная (синхронизируемая) оцифровка
     * 					                1 	- бесконечная (roll) оцифровка
     * Регистр зависит от: Период дискретизации TS.
     * Регистр RS применяется только если при выбранном интервале выборок (регистр TS) возможны два (или более) способа оцифровки.
     * От регистра зависят: Задержка развертки TD, обработка канала M1
     */
    @NonNull
    public BitSet setProcessingType(@NonNull BitSet values) throws IOException {
        Log.i(TAG, "setProcessingType: ", values);
        return BitSet.fromBytes(setRegistry("RS", Header.OSCILL_1BYTE, values.toBytes()));
    }

    /**
     * Имя свойства: TPl - Минимальный период параллельной/бесконечной дискретизации
     * Формат свойства: 4 байта, беззнаковый
     * Описание свойства: минимальное значение интервала параллельной дискретизации (и авто/ждущей, и бесконечной)
     * при условии, что усреднение/пиковый/статистический  режим не используются.
     * Единица измерения: машинные циклы, умноженные на 256
     * Свойство зависит от: скорости последовательного порта, длительности машинного цикла (MC), количества каналов,
     * режима (усреднение/пиковый) в канале
     * Пример свойства (базовая модель Oscill): TPl =0x01000000
     */
    public int getRollSamplingMinPeriod() throws IOException {
        return bytesToInt(getProperty("TPl", Header.OSCILL_4BYTE));
    }

    /**
     * Имя свойства: TOv - Быстрые варианты однократной дискретизации (realtime)
     * Описание свойства:  битовая карта всех вариантов однократной дискретизации, которые быстрее указанного в свойстве TOl..
     * Управляющее ПО должно отсутствующие варианты заменять предусмотренными, вычисляя длительность машинного цикла (регистр MC)
     * для достижения требуемого значения время/деление.
     * Формат свойства:  4 байта,  побитно: каждому биту соответствует определенное значение машинных циклов/выборку:
     * байт             TOv                         TOv+1
     * Номер бита       7   6   5   4   3   2   1   0   7   6   5   4   3   2   1   0
     * Clock/sample     -   30  29  28  27  26  25  24  23  22  21  20  19  18  17  16
     *
     * байт             TOv+2                       TOv+3
     * Номер бита       7   6   5   4   3   2   1   0   7   6   5   4   3   2   1   0
     * Clock/sample     15  14  13  12  11  10  9   8   7   6   5   4   3   2   1   1/2
     *
     * Единица измерения: бинарно: 1 - предусмотрено, 0 – не предусмотрено.
     * Свойство зависит от: нет.
     * Пример свойства (базовая модель Oscill): TOv =00000001 00000100
     */
    @NonNull
    public BitSet getSamplingVariants() throws IOException {
        return BitSet.fromBytes(getProperty("TOv", Header.OSCILL_4BYTE));
    }

    /**
     * Имя свойства: TMl - Минимальный период стробоскопической дискретизации (RIS)
     * Описание свойства: минимальное значение интервала эквивалентной дискретизации (для периодических сигналов)
     * Формат свойства:  2 байта, беззнаковый
     * Единица измерения: машинные циклы, умноженные на 256.
     * Свойство зависит от: нет.
     * Пример свойства (базовая модель Oscill): TMl =0x0010
     */
    public int getStroboscopeMinSamplingPeriod() throws IOException {
        return bytesToInt(getProperty("TMl", Header.OSCILL_2BYTE));
    }

    /**
     * Имя свойства: TMh - Максимальный период стробоскопической дискретизации (RIS)
     * Описание свойства: максимальное значение интервала эквивалентной дискретизации
     * (для периодических сигналов)
     * Формат свойства:  2 байта, беззнаковый
     * Единица измерения: машинные циклы, умноженные на 256
     * Свойство зависит от: нет.
     * Пример свойства (базовая модель Oscill): TMh =0x0100
     */
    public int getStroboscopeMaxSamplingPeriod() throws IOException {
        return bytesToInt(getProperty("TMh", Header.OSCILL_2BYTE));
    }

    /**
     * Имя свойства: TCh - Максимальное количество предвыборок
     * Формат свойства: 2 байта, беззнаковый
     * Описание свойства: максимальное количество выборок, которые возможно накопить перед моментом синхронизации
     * Единица измерения: выборка (может быть одно- и двухбайтовой)
     * Свойство зависит от: способа оцифровки RS, периода дискретизации TS, обработки выборок M1,
     * наличия усредняющих/пиконакопительных проходов  AP.
     */
    public int getMaxPreloadSamples() throws IOException {
        return bytesToInt(getProperty("TCh", Header.OSCILL_2BYTE));
    }

    /**
     * Имя свойства: QSh - Максимальный размер выходного массива
     * Описание свойства: количество выборок, которое может быть возвращено при данной дискретизации.
     * Формат свойства:  2 байта, беззнаковый
     * Единица измерения: выборка (может быть одно- и двухбайтовой)
     * Свойство зависит от: способа оцифровки RS + периода дискретизации TS (три набора), обработки выборок M1,
     * наличия усредняющих/пиконакопительных проходов  AP.
     */
    public int getMaxSamplesDataSize() throws IOException {
        return bytesToInt(getProperty("QSh", Header.OSCILL_2BYTE));
    }

    /**
     * Имя регистра: QS - Размер массива выборок
     * Формат регистра: 2 байта, беззнаковый
     * Описание регистра: количество выборок, возвращаемое при однократной, многократной и параллельной оцифровках.
     * Максимальное значение: свойство QSh
     * Регистр зависит от: способа оцифровки RS, периода дискретизации TS, обработки выборок M1.
     * От регистра зависят: нет.
     */
    public int setSamplesDataSize(int value) throws IOException {
        Log.i(TAG, "setSamplesDataSize: ", value);
        return bytesToInt(setRegistry("QS", Header.OSCILL_2BYTE, intTo2Bytes(value)));
    }

    public int getSamplesDataSize() throws IOException {
        return bytesToInt(getRegistry("QS", Header.OSCILL_2BYTE));
    }

    /**
     * Имя регистра: TC - Центровка развертки
     * Формат регистра: 2 байта, беззнаковый
     * Описание регистра: Интервал между первой выборкой и моментом синхронизации.
     * Позволяет наблюдать как предваряющий синхронизацию сигнал, так и сигнал, последующий за моментом синхронизации.
     * Единица измерения: выборки (то есть текущий интервал между выборками)
     * Диапазон изменения:  0….QS
     * Регистр зависит от: способа оцифровки RS, периода дискретизации TS, размера массива выборок QS.
     * Регистр теряет смысл при использовании задержки развертки (TD).
     */
    public int setSamplesOffset(int value) throws IOException {
        Log.i(TAG, "setSamplesOffset: ", value);
        return bytesToInt(setRegistry("TC", Header.OSCILL_2BYTE, intTo2Bytes(value)));
    }

    /**
     * Имя регистра: AP - Количество проходов при усреднении/пиковом режиме
     * Формат регистра: 1 байт. В регистре хранится количество проходов (значение должно быть степенью 2х) минус единица,
     * то есть возможно от одного до 256ти проходов.
     * Описание регистра:  На один запрос комп-а производится несколько циклов оцифровки (то есть необходимо несколько условий синхронизации),
     * результаты которых усредняются (или пиковые диапазоны выборок накладываются) AV раз, после чего итоговый массив возвращается комп-у.
     * Регистр зависит от: RS – многопроходность возможна только при однократном и стробоскопическом режиме.
     * Тип операции (усредение или накопление пиков) может быть в каждом канале свой, и определяется регистром M1 (для первого канала).
     * От регистра зависят: количество выборок QS и QSh
     */
    public byte setAvgSamplingCount(int value) throws IOException {
        Log.i(TAG, "setAvgSamplingCount: ", value);
        return setRegistry("AP", Header.OSCILL_1BYTE, intToByte(value))[0];
    }

    /**
     * Имя регистра: AR - Минимальное кол-во проходов в стробоскопич.режиме
     * Формат регистра: 1 байт, беззнаковый.
     * Описание регистра:  В стробоскопическом режиме производится серия оцифровок, из которых затем складывается выходной массив.
     * Каждая оцифровка характеризуется своей задержкой между стартом и моментом синхронизации. Оцифровки с одинаковой задержкой усредняются
     * или анализируются на мин/макс. Регистр AR указывает, какое минимальное количество оцифровок с одинаковой задержкой допускается.
     * Поскольку задержка оцифровки – случайная величина, для большинства требуемых задержек накопится больше оцифровок, чем задано в AR.
     * Регистр зависит от: нет
     * От регистра зависят:  нет
     */
    public byte setMinSamplingCount(int value) throws IOException {
        Log.i(TAG, "setMinSamplingCount: ", value);
        return setRegistry("AR", Header.OSCILL_1BYTE, intToByte(value))[0];
    }

    /**
     *
     */
    public int getScanDelayMin() throws IOException {
        return bytesToInt(getProperty("TDl", Header.OSCILL_4BYTE));
    }

    /**
     *
     */
    public int getScanDelayMax() throws IOException {
        return bytesToInt(getProperty("TDh", Header.OSCILL_4BYTE));
    }

    /**
     * Имя регистра: TD - Задержка развертки
     * Формат регистра: 4 байта, беззнаковый
     * Описание регистра: Задержка между моментом синхронизации и началом оцифровки.
     * Позволяет увидеть требуемый участок сигнала с хорошим разрешением по времени, несмотря на малую память.
     * Единица измерения: по 12 машинных циклов
     * Диапазон изменения: свойства TDl, TDh (зависят от RS, TS и QS)
     * Регистр зависит от: способа оцифровки RS, периода дискретизации TS, размера массива выборок QS
     * От регистра зависят: нет.
     */
    public int setScanDelay(int value) throws IOException {
        Log.i(TAG, "setScanDelay: ", value);
        return bytesToInt(setRegistry("TD", Header.OSCILL_4BYTE, intTo4Bytes(value)));
    }

    /**
     * Имя регистра: RT - Тип запуска
     * Формат регистра: 1 байт, побитный
     * Описание регистра: 	бит 10 :	------00  – автоматический запуск (после TA)
     * 				                    ------01  – ждущий запуск (лимит TW)
     * 				                    ------10  – свободный запуск
     * 				                    ------11  – бесконечно ждущий запуск
     * Регистр зависит от: нет
     * От регистра зависят: использование регистра TA или TW
     * Примечание: свободный и бесконечно ждущий запуски поддерживаются начиная с встроенного ПО (firmware) версии 1.25.
     */
    @NonNull
    public BitSet setSyncType(@NonNull BitSet bitSet) throws IOException {
        Log.i(TAG, "setSyncType: ", bitSet);
        return BitSet.fromBytes(setRegistry("RT", Header.OSCILL_1BYTE, bitSet.toBytes()));
    }

    @NonNull
    public BitSet getSyncType() throws IOException {
        return BitSet.fromBytes(getRegistry("RT", Header.OSCILL_1BYTE));
    }

    /**
     * Имя регистра: TA - Максимальное время ожидания синхронизации при автозапуске
     * Описание регистра: Синхронизация ожидается в течение указанного времени, а по его истечению – запускается оцифровка
     * (то есть возвращенные данные не будут синхронизированы).
     * Формат регистра: 4 байта, беззнаковый
     * Единица измерения: по 12 машинных циклов
     * Регистр зависит от:  действует при RT=0
     * От регистра зависят: нет.
     */
    public int setDelayMaxSyncAuto(int time) throws IOException{
        Log.i(TAG, "setDelayMaxSyncAuto: ", time);
        return bytesToInt(setRegistry("TA", Header.OSCILL_4BYTE, intTo4Bytes(time)));
    }

    /**
     * Имя регистра: TW - Макс. время ожидания синхронизации при ждущем запуске
     * Описание регистра: Синхронизация ожидается в течение указанного времени, а по его истечению – возвращается ошибка.
     * Формат регистра: 4 байта, беззнаковый
     * Единица измерения: по 12 машинных циклов
     * Регистр зависит от: действует при RT=1
     * От регистра зависят: нет.
     */
    public int setDelayMaxSyncWait(int time) throws IOException{
        Log.i(TAG, "setDelayMaxSyncWait: ", time);
        return bytesToInt(setRegistry("TW", Header.OSCILL_4BYTE, intTo4Bytes(time)));
    }

    /**
     * Имя свойства: V1h / V1l - Диапазон чувствительностей канала
     * Описание свойства: максимальная / минимальная чувствительность канала
     * Формат регистра: 2 байта, беззнаковый
     * Единица измерения:  8 мВ / диапазон АЦП
     * Свойство зависит от: нет.
     * Пример свойства (базовая модель Oscill): V1h=0x2710 (10В/дел), V1l=0x0014 (20мВ/дел)
     */
    public int getChanelSensitivityMin() throws IOException {
        return bytesToInt(getProperty("V1l", Header.OSCILL_2BYTE));
    }

    public int getChanelSensitivityMax() throws IOException {
        return bytesToInt(getProperty("V1h", Header.OSCILL_2BYTE));
    }

    /**
     * Имя свойства: P1h / P1l - Диапазон смещения в канале
     * Описание свойства: максимальные смещения входного диапазона АЦП относительно 0.
     * Формат регистра: 2 байта, знаковый
     * Единица измерения: 1/256я диапазона АЦП
     * Свойство зависит от: регистра V1. Для предотвращения ошибок рекомендуется запрашивать свойства после установки чувствительности.
     * Пример свойства (базовая модель Oscill): P1h=0x0180, P1l=0xFE80
     */
    public int getChanelOffsetMin() throws IOException {
        return signed(bytesToInt(getProperty("P1l", Header.OSCILL_2BYTE)));
    }

    public int getChanelOffsetMax() throws IOException {
        return signed(bytesToInt(getProperty("P1h", Header.OSCILL_2BYTE)));
    }

    /**
     * Имя свойства: D1m - Задержка синхронизации в канале
     * Описание свойства:  интервал времени между моментом синхронизации и его обработкой (конструктивная задержка в компараторе синхронизации,
     * определяемая быстродействием)
     * Формат регистра: 2 байта
     * Единица измерения: 10 пикосекунд
     * Свойство зависит от: уровня синхронизации S1 и режима синхронизации T1
     * Пример свойства (базовая модель Oscill): P1h=0x0180, P1l=0xFE80
     */
    public int getChanelDelay() throws IOException {
        return bytesToInt(getProperty("D1m", Header.OSCILL_2BYTE));
    }

    /**
     * Имя регистра: O1 - Аппаратный режим канала
     * Формат регистра: 1 байт
     * Описание регистра: 	Бит0: 	-------0 	– канал включен
     *                              -------1 	– вход заземлен
     * 			            Бит1: 	------0- 	– открытый вход (AC+DC)
     *                              ------1- 	– закрытый вход (AC)
     *  			        Бит2:	-----0-- 	– нет фильтрации 3МГц
     *                              -----1-- 	– включен фильтр 3МГц
     * 			            Бит3: 	----0--- 	– нет фильтрации 3кГц
     * 				                ----1--- 	– включен фильтр 3кГц (до 200мВ/дел)
     * От регистра зависят: нет
     * Регистр зависит от: нет.
     */
    public byte setChanelHWMode(@NonNull BitSet bitSet) throws IOException {
        Log.i(TAG, "setChanelHWMode: ", bitSet);
        return setRegistry("O1", Header.OSCILL_1BYTE, bitSet.toBytes())[0];
    }

    /**
     * Имя регистра: V1 - Чувствительность канала
     * Описание регистра: задает коэффициент усиления входного усилителя канала
     * Формат регистра: 2 байта, беззнаковый
     * Единица измерения:  8,53мВ / диапазон АЦП. При отображении 240ка уровней на 8и делениях экрана
     * единица регистра V1 будет соответствовать  1 мВ / деление.
     * Граничные значения: свойства V1h (максимальное значение В/дел, то есть низшая чувствительность),
     * V1l (минимальное значение В/дел, то есть наивысшая чувствительность)
     * Регистр зависит от: режима канала O1 (заземленный вход отменяет чувствительность)
     * От регистра зависят: смещение канала P1, диапазон смещений канала P1h / P1l .
     */
    public int setChanelSensitivity(int value) throws IOException {
        Log.i(TAG, "setChanelSensitivity: ", value);
        return bytesToInt(setRegistry("V1", Header.OSCILL_2BYTE, intTo2Bytes(value)));
    }

    public int getChanelSensitivity() throws IOException {
        return bytesToInt(getRegistry("V1", Header.OSCILL_2BYTE));
    }

    /**
     * Имя регистра: P1 - Смещение в канале
     * Описание регистра: смещение входного диапазона АЦП относительно 0.
     * Формат регистра: 2 байта, знаковый
     * Единица измерения: 1/256я входного диапазона АЦП
     * Граничные значения: свойства P1h (максимальное положительное смещение наблюдаемого диапазона),
     * P1l (максимальное отрицательное смещение наблюдаемого диапазона)
     * Регистр зависит от: чувствительности канала V1 (при минимальной чувствительности 10В/дел диапазон смещения более узок)
     * От регистра зависят: нет.
     */
    public int setChanelOffset(int value) throws IOException {
        Log.i(TAG, "setChanelOffset: ", value);
        return signed(bytesToInt(setRegistry("P1", Header.OSCILL_2BYTE, intTo2Bytes(value))));
    }

    public int getChanelOffset() throws IOException {
        return signed(bytesToInt(getRegistry("P1", Header.OSCILL_2BYTE)));
    }

    /**
     * Имя регистра: M1 - Программный режим канала (обработка выборок)
     * Формат регистра: 1 байт
     * Описание регистра: Биты 210:
     * -----000   – усреднение с отбрасыванием младших разрядов (1байт/выборка)
     * -----001   – усреднение  с повышением разрешения  (2 байта/выборка)
     * -----010   – пиковый режим – поочередно (2байта/2выборки)
     * -----011   – пиковый режим – повыборочно (2байта/выборка)
     * -----100   – обычный режим: байт массива = выборка АЦП (1байт/выборка)
     * Данный регистр относится к обработке, осуществляемой в Oscill-е. Кроме неё (или в дополнение к ней) аналогичная обработка может
     * осуществляться Comp-ом на основании нескольких подряд массивов выборок, полученных от Oscill.
     *  Количество проходов усреднения/накопления определяется регистром A1. При медленных развертках усреднение/накопление пиковых
     *  значений производится даже в течение одного прохода.
     * Регистр зависит от: RS (режимы невозможны при стробоскопической и параллельной оцифровках),
     * TS (режимы невозможны при малых периодах дискретизации)
     * От регистра зависят: количество выборок QS и QSh
     */
    public byte setChanelSWMode(@NonNull BitSet bitSet) throws IOException {
        Log.i(TAG, "setChanelSWMode: ", bitSet);
        return setRegistry("M1", Header.OSCILL_1BYTE, bitSet.toBytes())[0];
    }

    /**
     * Имя регистра: T1 - Использование канала для синхронизации
     * Формат регистра: 1 байт
     * Описание регистра: 	Бит4: 	---0---- 	– выключена синхронизация от спада
     * 				                ---1---- 	– включена синхронизация от спада
     *                      Бит5: 	--0----- 	– выключена синхронизация от фронта
     *                              --1----- 	– включена синхронизация от фронта
     * 			            Биты 1 0: 	------00	– гистерезис порога спада выключен
     *                                  ------11	– гистерезис порога спада включен
     * 			            Биты 3 2: 	----00--	– гистерезис порога фронта выключен
     *                                  ----11--	– гистерезис порога фронта включен
     *                      Биты 7 6 : 	00------ 	– ВЧ и НЧ синхронизация
     *                                  11------ 	– НЧ синхронизация
     * От регистра зависят: нет.
     * Регистр зависит от: нет.
     */
    @NonNull
    public BitSet setChanelSyncMode(@NonNull BitSet bitSet) throws IOException {
        Log.i(TAG, "setChanelSyncMode: ", bitSet);
        return BitSet.fromBytes(setRegistry("T1", Header.OSCILL_1BYTE, bitSet.toBytes()));
    }

    @NonNull
    public BitSet getChanelSyncMode() throws IOException {
        return BitSet.fromBytes(getRegistry("T1", Header.OSCILL_1BYTE));
    }

    /**
     * Имя регистра: S1 - Уровень синхронизации в канале
     * Формат регистра: 1 байт, беззнаковый
     * Описание регистра: уровень, при достижении которого в заданном регистром T1 направлении возникает событие синхронизации,
     * определяющее начало/окончание оцифровки.
     * Единица измерения: 1/256 от диапазона АЦП
     * Граничные значения: 0…255
     * От регистра зависят: нет.
     * Регистр зависит от: нет.
     */
    public int setChanelSyncLevel(int value) throws IOException {
        Log.i(TAG, "setChanelSyncLevel: ", value);
        return bytesToInt(setRegistry("S1", Header.OSCILL_1BYTE, intToByte(value)));
    }

    public int getChanelSyncLevel() throws IOException {
        return bytesToInt(getRegistry("S1", Header.OSCILL_1BYTE));
    }

    /**
     * Команда калибровки
     * По команде калибровки Oscill производит собственную калибровку
     * (масштабирование и привязку сдвига в канале и уровня синхронизации к входному диапазону АЦП).
     * Это обеспечивает установку нуля и правильность синхронизации и отображения.
     * Команда калибровки передаётся от Comp-а Oscill-у пакетом PUT с заголовком 0x72 “C”.
     * При успехе калибровки Oscill возвращает Response-пакет Success.
     */
    public void calibration() throws IOException {
        Log.i(TAG, "calibration");
        sendCommand("C", Header.OSCILL_EMPTY);
    }


    /**
     * Скорость последовательного порта во время сессии
     * (начало сессии всегда на скорости 9600 бод) определяется так: speed=1842000/коэфф.
     * Например, для скорости 115200 нужно установить коэффициент скорости =16 (0x10).
     */
    public void setSpeed(byte speed) throws IOException {
        Log.i(TAG, "setSpeed: ", 1842000 / speed);
        getClientSession().setSpeed(speed);
    }
}
