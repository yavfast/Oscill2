package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.BaseOscillMode;
import com.oscill.controller.Oscill;
import com.oscill.types.BitSet;

public class ChannelSyncMode extends BaseOscillMode {

    public ChannelSyncMode(@NonNull Oscill oscill) {
        super(oscill);
    }

    @NonNull
    @Override
    protected BitSet requestMode() throws Exception {
        return getOscill().getChanelSyncMode();
    }

    @NonNull
    @Override
    protected BitSet onModeChanged(@NonNull BitSet bitSet) throws Exception {
        return getOscill().setChanelSyncMode(bitSet);
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
    public ChannelSyncMode setHistBack(boolean enabled) throws Exception {
        apply(getMode().set(0, enabled).set(1, enabled));
        return this;
    }

    public boolean hasHistBack() {
        return getMode().get(0);
    }

    @NonNull
    public ChannelSyncMode setHistFront(boolean enabled) throws Exception {
        apply(getMode().set(2, enabled).set(3, enabled));
        return this;
    }

    public boolean hasHistFront() {
        return getMode().get(2);
    }

    @NonNull
    public ChannelSyncMode setSyncByBack(boolean enabled) throws Exception {
        apply(getMode().set(4, enabled));
        return this;
    }

    public boolean hasSyncByBack() {
        return getMode().get(4);
    }

    @NonNull
    public ChannelSyncMode setSyncByFront(boolean enabled) throws Exception {
        apply(getMode().set(5, enabled));
        return this;
    }

    public boolean hasSyncByFront() {
        return getMode().get(5);
    }

    @NonNull
    public ChannelSyncMode setLFSync(boolean enabled) throws Exception {
        apply(getMode().set(6, enabled).set(7, enabled));
        return this;
    }

    public boolean hasLFSync() {
        return getMode().get(6);
    }


}
