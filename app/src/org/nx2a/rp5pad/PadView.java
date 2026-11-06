package org.nx2a.rp5pad;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.view.View;

/** The controls as they are being held: all drawn in a 100 x 90 box scaled to the view. */
public class PadView extends View {
    static final int LIT = 0xFF22D3EE, FACE = 0xFF2A3440, MARK = 0xFF8A97A6, BODY = 0xFF182029;
    final PadActivity a;
    final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    final Drawable body;

    PadView(Context c, PadActivity a) {
        super(c);
        this.a = a;
        body = c.getDrawable(c.getResources().getIdentifier("pad_body", "drawable", c.getPackageName())).mutate();
        body.setTint(BODY);
        p.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        p.setSubpixelText(true);
        p.setLinearText(true);   // the canvas is scaled: hinted widths at these tiny sizes overlap
    }

    void dot(Canvas c, float x, float y, float r, boolean on) {
        p.setStyle(Paint.Style.FILL);
        p.setColor(on ? LIT : FACE);
        c.drawCircle(x, y, r, p);
    }

    void label(Canvas c, String s, float x, float y, float size, boolean on) {
        p.setStyle(Paint.Style.FILL);
        p.setColor(on ? Color.BLACK : MARK);
        p.setTextSize(size);
        p.setTextAlign(Paint.Align.CENTER);
        c.drawText(s, x, y + size * 0.36f, p);
    }

    void pill(Canvas c, float l, float t, float r, float b, boolean on) {
        p.setStyle(Paint.Style.FILL);
        p.setColor(on ? LIT : FACE);
        c.drawRoundRect(new RectF(l, t, r, b), (b - t) / 2, (b - t) / 2, p);
    }

    void trigger(Canvas c, float l, float r, float v, String s, boolean fromRight) {
        pill(c, l, 6, r, 11, false);
        if (v > 0.01f) {
            float w = Math.max(5, (r - l) * v);
            if (fromRight) pill(c, r - w, 6, r, 11, true); else pill(c, l, 6, l + w, 11, true);
        }
        label(c, s, (l + r) / 2, 8.5f, 2.8f, v > 0.5f);
    }

    void stick(Canvas c, float x, float y, float sx, float sy, boolean pressed) {
        p.setStyle(Paint.Style.FILL);
        p.setColor(0xFF10161C);
        c.drawCircle(x, y, 7.2f, p);
        boolean moved = Math.abs(sx) > 0.1f || Math.abs(sy) > 0.1f;
        dot(c, x + sx * 3.4f, y + sy * 3.4f, 3.8f, pressed || moved);
    }

    @Override protected void onDraw(Canvas c) {
        int k;
        float lx, ly, rx, ry, lt, rt;
        synchronized (a.lock) {
            k = a.keys | a.hat;
            lx = a.lx; ly = a.ly; rx = a.rx; ry = a.ry;
            lt = a.l2 ? 1 : a.lta;
            rt = a.r2 ? 1 : a.rta;
        }
        float s = Math.min(getWidth() / 100f, getHeight() / 90f);
        c.save();
        c.translate((getWidth() - 100 * s) / 2, (getHeight() - 90 * s) / 2);
        c.scale(s, s);
        body.setBounds(0, 0, 100, 100);
        c.save();
        c.translate(0, -2);
        body.draw(c);
        c.restore();
        trigger(c, 14, 38, lt, "LT", false);
        trigger(c, 62, 86, rt, "RT", true);
        boolean lb = (k & PadActivity.LB) != 0, rb = (k & PadActivity.RB) != 0;
        pill(c, 14, 13, 38, 18, lb);
        label(c, "LB", 26, 15.5f, 2.8f, lb);
        pill(c, 62, 13, 86, 18, rb);
        label(c, "RB", 74, 15.5f, 2.8f, rb);
        // D-pad
        float dx = 21, dy = 37;
        pill(c, dx - 1.9f, dy - 6.8f, dx + 1.9f, dy - 1, (k & PadActivity.UP) != 0);
        pill(c, dx - 1.9f, dy + 1, dx + 1.9f, dy + 6.8f, (k & PadActivity.DOWN) != 0);
        pill(c, dx - 6.8f, dy - 1.9f, dx - 1, dy + 1.9f, (k & PadActivity.LEFT) != 0);
        pill(c, dx + 1, dy - 1.9f, dx + 6.8f, dy + 1.9f, (k & PadActivity.RIGHT) != 0);
        // Face buttons
        float fx = 79, fy = 37, o = 5.4f, r = 2.7f;
        String[] n = {"Y", "A", "X", "B"};
        int[] m = {PadActivity.Y, PadActivity.A, PadActivity.X, PadActivity.B};
        float[][] at = {{fx, fy - o}, {fx, fy + o}, {fx - o, fy}, {fx + o, fy}};
        for (int i = 0; i < 4; i++) {
            boolean on = (k & m[i]) != 0;
            dot(c, at[i][0], at[i][1], r, on);
            label(c, n[i], at[i][0], at[i][1], 3f, on);
        }
        pill(c, 42, 30, 47.5f, 33, (k & PadActivity.BACK) != 0);
        pill(c, 52.5f, 30, 58, 33, (k & PadActivity.START) != 0);
        stick(c, 36, 49, lx, ly, (k & PadActivity.L3) != 0);
        stick(c, 64, 49, rx, ry, (k & PadActivity.R3) != 0);
        c.restore();
    }
}
