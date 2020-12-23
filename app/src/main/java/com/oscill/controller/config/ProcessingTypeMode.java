package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.BaseOscillMode;
import com.oscill.controller.Oscill;
import com.oscill.types.BitSet;

public class ProcessingTypeMode extends BaseOscillMode {

    public ProcessingTypeMode(@NonNull Oscill oscill) {
        super(oscill);
    }

    @NonNull
    @Override
    protected BitSet requestMode() throws Exception {
        return getOscill().getProcessingType();
    }

    @NonNull
    @Override
    protected BitSet onModeChanged(@NonNull BitSet bitSet) throws Exception {
        return getOscill().setProcessingType(bitSet);
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

    public enum ProcessingType {
        REALTIME, RIS
    }

    public enum DataOutputType {
        POST_PROCESSING, REALTIME
    }

    public enum BufferType {
        SYNC, ROLL
    }

    @NonNull
    public ProcessingTypeMode setProcessingType(@NonNull ProcessingType type) throws Exception {
        apply(getMode().set(0, type == ProcessingType.RIS));
        return this;
    }

    @NonNull
    public ProcessingType getProcessingType() {
        return getMode().get(0) ? ProcessingType.RIS : ProcessingType.REALTIME;
    }

    @NonNull
    public ProcessingTypeMode setDataOutputType(@NonNull DataOutputType type) throws Exception {
        apply(getMode().set(1, type == DataOutputType.REALTIME));
        return this;
    }

    @NonNull
    public DataOutputType getDataOutputType() {
        return getMode().get(1) ? DataOutputType.REALTIME : DataOutputType.POST_PROCESSING;
    }

    @NonNull
    public ProcessingTypeMode setBufferType(@NonNull BufferType type) throws Exception {
        apply(getMode().set(2, type == BufferType.ROLL));
        return this;
    }

    @NonNull
    public BufferType getBufferType() {
        return getMode().get(2) ? BufferType.ROLL : BufferType.SYNC;
    }
}
