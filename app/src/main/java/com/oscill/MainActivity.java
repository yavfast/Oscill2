package com.oscill;

import android.graphics.Color;
import android.os.Bundle;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;

import com.github.mikephil.charting.charts.LineChart;
import com.github.mikephil.charting.components.XAxis;
import com.github.mikephil.charting.components.YAxis;
import com.github.mikephil.charting.data.Entry;
import com.github.mikephil.charting.data.LineData;
import com.github.mikephil.charting.data.LineDataSet;
import com.github.mikephil.charting.interfaces.datasets.ILineDataSet;
import com.oscill.controller.Oscill;
import com.oscill.controller.OscillData;
import com.oscill.controller.OscillManager;
import com.oscill.controller.config.ChanelSWMode;
import com.oscill.controller.config.ProcessingTypeMode;
import com.oscill.controller.config.Sensitivity;
import com.oscill.controller.config.SyncTypeMode;
import com.oscill.events.OnOscillConnected;
import com.oscill.events.OnOscillData;
import com.oscill.events.OnOscillError;
import com.oscill.types.Dimension;
import com.oscill.utils.Log;
import com.oscill.utils.ViewUtils;
import com.oscill.utils.executor.EventHolder;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.Executor;

import java.util.ArrayList;

public class MainActivity extends AppCompatActivity {

    private final static String TAG = Log.getTag(MainActivity.class);

    private LineChart chart;

    private final EventHolder<?> onOscillConnected = EventsController.onReceiveEvent(this, OnOscillConnected.class, event ->
            onOscillConnected()
    );

    private final EventHolder<?> onOscillData = EventsController.onReceiveEventAsync(this, OnOscillData.class, event ->
            prepareData(event.oscillData)
    );

    private final EventHolder<?> onOscillError = EventsController.onReceiveEvent(this, OnOscillError.class, event ->
            onOscillError(event.getError())
    );

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);

        initChart();
        chart.setOnClickListener(v ->
                OscillManager.requestNextData()
        );

        EventsController.resumeEvents(onOscillConnected, onOscillData, onOscillError);
        connectToDevice();
    }

    @Override
    protected void onResume() {
        super.onResume();
        EventsController.resumeEvents(onOscillConnected, onOscillData, onOscillError);
    }

    @Override
    protected void onPause() {
        EventsController.pauseEvents(onOscillConnected, onOscillData, onOscillError);
        OscillManager.pause();
        super.onPause();
    }

    private void connectToDevice() {
        if (OscillManager.isConnected()) {
            OscillManager.requestNextData();
        } else {
            OscillManager.init();
        }
    }

    private void onOscillConnected() {
        OscillManager.runConfigTask(oscillConfig -> {
            try {
                Oscill oscill = oscillConfig.getOscill();

                oscillConfig.getCpuTickLength().setCPUFreq(60, Dimension.MEGA);

                oscillConfig.getProcessingTypeMode()
                        .setProcessingType(ProcessingTypeMode.ProcessingType.REALTIME)
                        .setDataOutputType(ProcessingTypeMode.DataOutputType.POST_PROCESSING)
                        .setBufferType(ProcessingTypeMode.BufferType.SYNC);

                oscill.setScanDelay(0); // TD

                oscill.setDelayMaxSyncAuto(500); // TA
                oscill.setDelayMaxSyncWait(500); // TW

                oscill.setMinSamplingCount(0); // AR
                oscill.setAvgSamplingCount(0); // AP

                oscillConfig.getChanelHWMode()
                        .setChanelEnabled(true)
                        .setACMode(false)
                        .setFilter3kHz(false)
                        .setFilter3MHz(false);

                oscillConfig.getChanelSWMode().setSWMode(ChanelSWMode.SWMode.NORMAL);

                oscillConfig.getChanelSensitivity().setSensitivity(Sensitivity._200_mV);
                oscillConfig.getChanelOffset().setOffset(0f, Dimension.MILLI);

                oscillConfig.getChanelSyncMode()
                        .setSyncByFront(true)
                        .setHistFront(false);

                oscillConfig.getChanelSyncLevel().setNativeValue(20);
                oscillConfig.getSyncTypeMode().setSyncType(SyncTypeMode.SyncType.FREE);

                // WARN: set last
                oscillConfig.getSamplesCount().setSamplesCount(10, 50);
                oscillConfig.getSamplingPeriod().setSamplingPeriod(5f, Dimension.MILLI);
                oscillConfig.getSamplesOffset().setOffset(10f, Dimension.MILLI);

                oscill.calibration();

                OscillManager.start();
            } catch (Exception e) {
                onOscillError(e);
            }
        });
    }

    private void onOscillError(@NonNull Throwable e) {
        Log.e(TAG, e);
        ViewUtils.showToast(e.getMessage());
    }

    private void initChart() {
        chart = findViewById(R.id.chart);

        chart.setBackgroundColor(Color.DKGRAY);
        chart.getDescription().setEnabled(false);
        chart.getLegend().setEnabled(false);

        chart.setDrawBorders(true);
        chart.setBorderColor(Color.GRAY);

        chart.setDrawGridBackground(false);
        chart.setTouchEnabled(true);
        chart.setDragEnabled(true);
        chart.setScaleEnabled(true);
        chart.setPinchZoom(true);

        XAxis xAxis = chart.getXAxis();
        xAxis.setGridColor(Color.GRAY);
        xAxis.setAxisLineColor(Color.GRAY);
        xAxis.setTextColor(Color.WHITE);
        xAxis.setAvoidFirstLastClipping(false);
        xAxis.enableGridDashedLine(2f, 2f, 0f);
        xAxis.setDrawGridLinesBehindData(false);

        YAxis yAxisLeft = chart.getAxisLeft();
        YAxis yAxisRight = chart.getAxisRight();

        yAxisLeft.enableGridDashedLine(2f, 2f, 0f);
        yAxisLeft.setDrawGridLinesBehindData(false);
        yAxisLeft.setZeroLineWidth(2f);
        yAxisLeft.setGridColor(Color.GRAY);
        yAxisLeft.setAxisLineColor(Color.GRAY);
        yAxisLeft.setTextColor(Color.WHITE);

        yAxisRight.enableGridDashedLine(2f, 2f, 0f);
        yAxisRight.setDrawGridLinesBehindData(false);
        yAxisRight.setZeroLineWidth(2f);
        yAxisRight.setGridColor(Color.GRAY);
        yAxisRight.setAxisLineColor(Color.GRAY);
        yAxisRight.setTextColor(Color.WHITE);

    }

    private void prepareData(@NonNull OscillData oscillData) {
        float[] tData = oscillData.tData;
        float[] vData = oscillData.vData;
        int dataSize = oscillData.dataSize;

        ArrayList<Entry> values = new ArrayList<>(dataSize);
        for (int idx = 0; idx < dataSize; idx++) {
            values.add(new Entry(tData[idx], vData[idx]));
        }

        Executor.runInUIThreadAsync(() -> setData(oscillData, values));
    }

    private void setData(@NonNull OscillData oscillData, @NonNull ArrayList<Entry> values) {
        YAxis yAxisLeft = chart.getAxisLeft();
        YAxis yAxisRight = chart.getAxisRight();
        float maxV = oscillData.getMaxV();
        float minV = oscillData.getMinV();
        yAxisLeft.setAxisMaximum(maxV);
        yAxisLeft.setAxisMinimum(minV);
        yAxisRight.setAxisMaximum(maxV);
        yAxisRight.setAxisMinimum(minV);

        LineDataSet dataSet;
        LineData data = chart.getData();

        if (data != null && data.getDataSetCount() > 0) {
            dataSet = (LineDataSet) data.getDataSetByIndex(0);
            dataSet.setValues(values);
            dataSet.notifyDataSetChanged();
            data.notifyDataChanged();
            chart.notifyDataSetChanged();
            chart.invalidate();

        } else {
            dataSet = new LineDataSet(values, null);

            dataSet.setDrawIcons(false);
            dataSet.setDrawCircles(false);
            dataSet.setDrawCircleHole(false);
            dataSet.setDrawValues(false);
            dataSet.setDrawFilled(false);

            dataSet.setColor(Color.CYAN);
            dataSet.setLineWidth(2f);

            ArrayList<ILineDataSet> dataSets = new ArrayList<>();
            dataSets.add(dataSet);

            data = new LineData(dataSets);
            chart.setData(data);
        }
    }

}
