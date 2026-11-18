<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

class scorechart {
    public static function svg(array $clos, int $width = 640, int $height = 360): string {
        $n = count($clos);
        if ($n < 1) {
            return '';
        }
        $left = 64; $right = 64; $top = 64; $bottom = 78;
        $pw = $width - $left - $right;
        $ph = $height - $top - $bottom;
        $slot = $pw / $n;
        $bw = min(130, $slot * 0.6);
        $y = fn(float $v): float => round($top + $ph * (1 - max(0, min(100, $v)) / 100), 1);
        $font = "font-family=\"Georgia,'Times New Roman',serif\"";
        $svg = "<svg class=\"local-clo-scorechart\" viewBox=\"0 0 $width $height\" width=\"100%\" style=\"max-width:{$width}px\" "
             . "role=\"img\" aria-label=\"" . s(get_string('scorechart', 'local_clo')) . "\">";
        $svg .= "<text x=\"" . ($width / 2) . "\" y=\"28\" text-anchor=\"middle\" font-size=\"19\" font-weight=\"700\" fill=\"#333\" $font>"
              . s(get_string('scorechart', 'local_clo')) . '</text>';
        foreach ([0, 25, 50, 75, 100] as $g) {
            $gy = $y($g);
            $svg .= "<line x1=\"$left\" y1=\"$gy\" x2=\"" . ($width - $right) . "\" y2=\"$gy\" stroke=\"" . ($g ? '#e5e7eb' : '#9ca3af') . "\"/>";
            $svg .= "<text x=\"" . ($left - 8) . "\" y=\"" . ($gy + 4) . "\" text-anchor=\"end\" font-size=\"12\" fill=\"#667085\" $font>$g%</text>";
        }
        $linepts = [];
        $labels = '';
        foreach (array_values($clos) as $i => $clo) {
            $cx = round($left + $slot * ($i + 0.5), 1);
            $pct = (float)($clo->pct ?? 0);
            $by = $y($pct);
            $svg .= "<rect x=\"" . round($cx - $bw / 2, 1) . "\" y=\"$by\" width=\"" . round($bw, 1) . "\" height=\"" . round($top + $ph - $by, 1)
                  . "\" fill=\"#516cc6\"/>";
            $labels .= "<text x=\"$cx\" y=\"" . ($by - 10) . "\" text-anchor=\"middle\" font-size=\"13\" fill=\"#333\" stroke=\"#fff\" stroke-width=\"3\" "
                     . "paint-order=\"stroke\" $font>" . format_float($pct, 1) . '</text>';
            $svg .= "<text x=\"$cx\" y=\"" . ($top + $ph + 22) . "\" text-anchor=\"middle\" font-size=\"13\" font-weight=\"700\" fill=\"#344054\" $font>"
                  . s($clo->code) . '</text>';
            if (isset($clo->class_avg)) {
                $linepts[] = [$cx, $y((float)$clo->class_avg)];
            }
        }
        if ($linepts) {
            $svg .= '<polyline points="' . implode(' ', array_map(fn($p) => $p[0] . ',' . $p[1], $linepts))
                  . '" fill="none" stroke="#91cc75" stroke-width="2.5"/>';
            foreach ($linepts as $p) {
                $svg .= "<circle cx=\"{$p[0]}\" cy=\"{$p[1]}\" r=\"5\" fill=\"#fff\" stroke=\"#91cc75\" stroke-width=\"2.5\"/>";
            }
        }
        $svg .= $labels;
        $ly = $height - 22;
        $mx = $width / 2;
        $svg .= "<line x1=\"" . ($mx - 150) . "\" y1=\"$ly\" x2=\"" . ($mx - 110) . "\" y2=\"$ly\" stroke=\"#91cc75\" stroke-width=\"2.5\"/>";
        $svg .= "<circle cx=\"" . ($mx - 130) . "\" cy=\"$ly\" r=\"5\" fill=\"#fff\" stroke=\"#91cc75\" stroke-width=\"2.5\"/>";
        $svg .= "<text x=\"" . ($mx - 102) . "\" y=\"" . ($ly + 4) . "\" font-size=\"13\" fill=\"#333\" $font>" . s(get_string('legend_avg', 'local_clo')) . '</text>';
        $svg .= "<rect x=\"" . ($mx + 40) . "\" y=\"" . ($ly - 7) . "\" width=\"26\" height=\"14\" fill=\"#516cc6\"/>";
        $svg .= "<text x=\"" . ($mx + 74) . "\" y=\"" . ($ly + 4) . "\" font-size=\"13\" fill=\"#333\" $font>" . s(get_string('legend_me', 'local_clo')) . '</text>';
        return $svg . '</svg>';
    }
}
