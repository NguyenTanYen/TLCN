<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

/**
 * Biểu đồ radar (SVG thuần, không cần JavaScript) so sánh mức đạt từng CLO của sinh viên
 * với ngưỡng kỳ vọng θk và trung bình lớp.
 */
class radar {
    public static function svg(array $clos, int $size = 340): string {
        $n = count($clos);
        if ($n < 3) {
            return '';
        }
        $c = $size / 2; $r = $size / 2 - 58;
        $pt = function (int $i, float $v) use ($n, $c, $r): array {
            $a = -M_PI / 2 + 2 * M_PI * $i / $n;
            $d = $r * max(0, min(100, $v)) / 100;
            return [round($c + $d * cos($a), 1), round($c + $d * sin($a), 1)];
        };
        $poly = function (array $vals) use ($pt): string {
            $out = [];
            foreach (array_values($vals) as $i => $v) {
                $out[] = implode(',', $pt($i, (float)$v));
            }
            return implode(' ', $out);
        };
        $svg = "<svg class=\"local-clo-radar\" viewBox=\"0 0 $size $size\" width=\"100%\" style=\"max-width:{$size}px\" "
             . "role=\"img\" aria-label=\"" . s(get_string('radar', 'local_clo')) . "\">";
        foreach ([25, 50, 75, 100] as $g) {
            $svg .= '<polygon points="' . $poly(array_fill(0, $n, $g)) . '" fill="none" stroke="#d0d5dd" stroke-width="1"/>';
        }
        foreach ($clos as $i => $clo) {
            [$x, $y] = $pt($i, 100);
            $svg .= "<line x1=\"$c\" y1=\"$c\" x2=\"$x\" y2=\"$y\" stroke=\"#d0d5dd\"/>";
            [$lx, $ly] = $pt($i, 122);
            $anchor = abs($lx - $c) < 8 ? 'middle' : ($lx > $c ? 'start' : 'end');
            $svg .= "<text x=\"$lx\" y=\"$ly\" text-anchor=\"$anchor\" dominant-baseline=\"middle\" font-size=\"12\" "
                  . "font-weight=\"600\" fill=\"#344054\">" . s($clo->code) . '</text>';
        }
        $svg .= '<text x="' . ($c + 3) . '" y="' . ($c - $r / 2) . '" font-size="9" fill="#98a2b3">50%</text>';
        $svg .= '<polygon points="' . $poly(array_map(fn($x) => $x->class_avg ?? 0, $clos))
              . '" fill="none" stroke="#98a2b3" stroke-width="1.5" stroke-dasharray="2 3"/>';
        $svg .= '<polygon points="' . $poly(array_map(fn($x) => $x->threshold ?? 0, $clos))
              . '" fill="none" stroke="#f79009" stroke-width="2" stroke-dasharray="6 4"/>';
        $svg .= '<polygon points="' . $poly(array_map(fn($x) => $x->pct ?? 0, $clos))
              . '" fill="rgba(11,61,145,.22)" stroke="#0b3d91" stroke-width="2.5"/>';
        foreach ($clos as $i => $clo) {
            [$x, $y] = $pt($i, (float)($clo->pct ?? 0));
            $svg .= "<circle cx=\"$x\" cy=\"$y\" r=\"3.5\" fill=\"#0b3d91\"/>";
        }
        return $svg . '</svg>';
    }
}
