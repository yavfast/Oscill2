package com.oscill;

import android.graphics.Color;
import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;

import com.github.mikephil.charting.charts.LineChart;
import com.github.mikephil.charting.components.XAxis;
import com.github.mikephil.charting.components.YAxis;
import com.github.mikephil.charting.data.Entry;
import com.github.mikephil.charting.data.LineData;
import com.github.mikephil.charting.data.LineDataSet;
import com.github.mikephil.charting.interfaces.datasets.ILineDataSet;

import java.util.ArrayList;

public class MainActivity extends AppCompatActivity {

    private LineChart chart;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);

        initChart();
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
        yAxisLeft.setGridColor(Color.GRAY);
        yAxisLeft.setAxisLineColor(Color.GRAY);
        yAxisLeft.setTextColor(Color.WHITE);
        yAxisLeft.setAxisMaximum(100f);
        yAxisLeft.setAxisMinimum(-100f);

        yAxisRight.enableGridDashedLine(2f, 2f, 0f);
        yAxisRight.setDrawGridLinesBehindData(false);
        yAxisRight.setGridColor(Color.GRAY);
        yAxisRight.setAxisLineColor(Color.GRAY);
        yAxisRight.setTextColor(Color.WHITE);
        yAxisRight.setAxisMaximum(100f);
        yAxisRight.setAxisMinimum(-100f);

        setData(500, 180);

    }

    private void setData(int count, float range) {

        ArrayList<Entry> values = new ArrayList<>();

        for (int i = 0; i < count; i++) {
            float val = (float) ((Math.random() * range) - (range / 2f)) * 0.1f;
            values.add(new Entry(i, val));
        }

        LineDataSet dataSet;
        LineData data = chart.getData();

        if (data != null && data.getDataSetCount() > 0) {
            dataSet = (LineDataSet) data.getDataSetByIndex(0);
            dataSet.setValues(values);
            dataSet.notifyDataSetChanged();
            data.notifyDataChanged();
            chart.notifyDataSetChanged();

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
