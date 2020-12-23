package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.BaseOscillMode;
import com.oscill.controller.Oscill;
import com.oscill.types.BitSet;

public class ChanelHWMode extends BaseOscillMode {

    public ChanelHWMode(@NonNull Oscill oscill) {
        super(oscill);
    }

    @NonNull
    @Override
    protected BitSet requestMode() throws Exception {
        return getOscill().getChanelHWMode();
    }

    @NonNull
    @Override
    protected BitSet onModeChanged(@NonNull BitSet bitSet) throws Exception {
        return getOscill().setChanelHWMode(bitSet);
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

    @NonNull
    public ChanelHWMode setChanelEnabled(boolean enabled) throws Exception {
        apply(getMode().set(0, !enabled));
        return this;
    }

    public boolean isChanelEnabled() {
        return getMode().get(0);
    }

    @NonNull
    public ChanelHWMode setACMode(boolean enabled) throws Exception {
        apply(getMode().set(1, enabled));
        return this;
    }

    public boolean isACModeEnabled() {
        return getMode().get(1);
    }

    @NonNull
    public ChanelHWMode setFilter3MHz(boolean enabled) throws Exception {
        apply(getMode().set(2, enabled));
        return this;
    }

    public boolean isFilter3MHzEnabled() {
        return getMode().get(2);
    }

    @NonNull
    public ChanelHWMode setFilter3kHz(boolean enabled) throws Exception {
        apply(getMode().set(3, enabled));
        return this;
    }

    public boolean isFilter3kHzEnabled() {
        return getMode().get(3);
    }
}
