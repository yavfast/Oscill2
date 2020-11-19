package com.oscill.obex;

import androidx.annotation.NonNull;

import com.oscill.utils.Log;

import java.io.IOException;
import java.util.BitSet;

public class Oscill extends BaseOscillController {

    private static final String TAG = Log.getTag(Oscill.class);

    public Oscill(@NonNull ClientSession clientSession) {
        super(clientSession);
    }

    public int connect() throws IOException {
        return getClientSession().connect(null).getResponseCode();
    }

    @NonNull
    public String getDeviceId() throws IOException {
        return bytesToString(getProperty("VNM", HeaderSet.OSCILL_4BYTE));
    }

    @NonNull
    public String getDeviceSerialNumber() throws IOException {
        return bytesToString(getProperty("VSN", HeaderSet.OSCILL_4BYTE));
    }

    @NonNull
    public String getDeviceHardwareVersion() throws IOException {
        return bytesToString(getProperty("VHW", HeaderSet.OSCILL_4BYTE));
    }

    @NonNull
    public String getDeviceSoftwareVersion() throws IOException {
        return bytesToString(getProperty("VSW", HeaderSet.OSCILL_4BYTE));
    }

    /**
     * Имя свойства: MCd - Длительность машинного цикла по умолчанию
     * Формат свойства: 2 байта, беззнаковое
     * Описание свойства: длительность машинного цикла процессора, гарантированно обеспечивающая егостабильную работу
     * Единица измерения: по 10 пс
     * Пример свойства (базовая модель Oscill): MCd=0x07D0 (50МГц тактовая частота)
     */
    public int getCPUTickDefLength() throws IOException {
        return bytesToInt(getProperty("MCd", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(getProperty("MCl", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(setRegistry("MC", HeaderSet.OSCILL_2BYTE, intToBytes(value)));
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
        return bytesToInt(getProperty("TOl", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(setRegistry("TS", HeaderSet.OSCILL_4BYTE, intToBytes(value)));
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
        return bytesToBits(setRegistry("RS", HeaderSet.OSCILL_1BYTE, bitsToBytes(values)));
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
        return bytesToInt(getProperty("TPl", HeaderSet.OSCILL_4BYTE));
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
     * Единица измерения: бинарно: 1=предусмотрено, 0 – не предусмотрено.
     * Свойство зависит от: нет.
     * Пример свойства (базовая модель Oscill): TOv =00000001 00000100
     */
    @NonNull
    public BitSet getSamplingVariants() throws IOException {
        return bytesToBits(getProperty("TOv", HeaderSet.OSCILL_4BYTE));
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
        return bytesToInt(getProperty("TMl", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(getProperty("TMh", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(getProperty("TCh", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(getProperty("QSh", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(setRegistry("QS", HeaderSet.OSCILL_2BYTE, intToBytes(value)));
    }

    /**
     * Имя регистра: TC - Центровка развертки
     * Формат регистра: 2 байта, беззнаковый
     * Описание регистра: Интервал между первой выборкой и моментом синхронизации.
     * Позволяет наблюдать как предваряющий синхронизацию сигнал, так и сигнал,  последующий за моментом синхронизации.
     * Единица измерения: выборки (то есть текущий интервал между выборками)
     * Диапазон изменения:  0….QS
     * Регистр зависит от: способа оцифровки RS, периода дискретизации TS, размера массива выборок QS.
     * Регистр теряет смысл при использовании задержки развертки (TD).
     */
    public int setSamplesOffset(int value) throws IOException {
        return bytesToInt(setRegistry("TC", HeaderSet.OSCILL_2BYTE, intToBytes(value)));
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
    public byte setAvgSamplingCount(byte value) throws IOException {
        return setRegistry("AP", HeaderSet.OSCILL_1BYTE, new byte[]{value})[0];
    }

    /**
     *
     */
    public int getScanDelayMin() throws IOException {
        return bytesToInt(getProperty("TDl", HeaderSet.OSCILL_4BYTE));
    }

    /**
     *
     */
    public int getScanDelayMax() throws IOException {
        return bytesToInt(getProperty("TDh", HeaderSet.OSCILL_4BYTE));
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
        return bytesToInt(setRegistry("TD", HeaderSet.OSCILL_4BYTE, intToBytes(value)));
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
    public void setSyncType(byte syncType) throws IOException {
        setRegistry("RT", HeaderSet.OSCILL_1BYTE, new byte[]{syncType});
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
        return bytesToInt(getProperty("V1l", HeaderSet.OSCILL_2BYTE));
    }

    public int getChanelSensitivityMax() throws IOException {
        return bytesToInt(getProperty("V1h", HeaderSet.OSCILL_2BYTE));
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
        return bytesToInt(getProperty("P1l", HeaderSet.OSCILL_2BYTE)); // TODO: signed
    }

    public int getChanelOffsetMax() throws IOException {
        return bytesToInt(getProperty("P1h", HeaderSet.OSCILL_2BYTE)); // TODO: signed
    }

    /**
     * Имя свойства: D1m - Задержка синхронизации в канале
     * Описание свойства:  интервал времени между моментом синхронизации и его обработкой (конструктивная задержка в компараторе синхронизации, определяемая быстродействием)
     * Формат регистра: 2 байта
     * Единица измерения: 10 пикосекунд
     * Свойство зависит от: уровня синхронизации S1 и режима синхронизации T1
     * Пример свойства (базовая модель Oscill): P1h=0x0180, P1l=0xFE80
     */
    public int getChanelDelay() throws IOException {
        return bytesToInt(getProperty("D1m", HeaderSet.OSCILL_2BYTE));
    }

}
