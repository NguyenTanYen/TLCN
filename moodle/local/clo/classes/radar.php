<?php
namespace local_clo;

defined('MOODLE_INTERNAL') || die();

class radar {
    private static function marker(string $kind, float $x, float $y, string $color): string {
        switch ($kind) {
            case 'diamond':
                $p = [[$x, $y - 5.5], [$x + 5.5, $y], [$x, $y + 5.5], [$x - 5.5, $y]];
                return '<polygon points="' . implode(' ', array_map(fn($q) => $q[0] . ',' . $q[1], $p)) . "\" fill=\"$color\"/>";
            case 'square':
                return '<rect x="' . ($x - 4.5) . '" y="' . ($y - 4.5) . "\" width=\"9\" height=\"9\" fill=\"$color\"/>";
            default:
                $p = [[$x, $y - 6], [$x + 5.5, $y + 4.5], [$x - 5.5, $y + 4.5]];
                return '<polygon points="' . implode(' ', array_map(fn($q) => $q[0] . ',' . $q[1], $p)) . "\" fill=\"$color\"/>";
        }
    }

    private static function wrap(string $text, int $max = 14): array {
        $lines = [];
        $cur = '';
        foreach (preg_split('/\s+/', trim($text)) as $w) {
            if ($cur !== '' && mb_strlen($cur . ' ' . $w) > $max) {
                $lines[] = $cur;
                $cur = $w;
            } else {
                $cur = $cur === '' ? $w : $cur . ' ' . $w;
            }
        }
        if ($cur !== '') {
            $lines[] = $cur;
        }
        return $lines ?: [''];
    }

    public static function svg(array $clos, int $width = 720, int $height = 440): string {
        $n = count($clos);
        if ($n < 3) {
            return '';
        }
        $cx = 270; $cy = 225; $r = 150;
        $pt = function (int $i, float $v, float $extra = 0) use ($n, $cx, $cy, $r): array {
            $a = -M_PI / 2 + 2 * M_PI * $i / $n;
            $d = $r * max(0, min(100, $v)) / 100 + $extra;
            return [round($cx + $d * cos($a), 1), round($cy + $d * sin($a), 1)];
        };
        $poly = function (array $vals) use ($pt): string {
            $out = [];
            foreach (array_values($vals) as $i => $v) {
                $out[] = implode(',', $pt($i, (float)$v));
            }
            return implode(' ', $out);
        };
        $font = "font-family=\"'Segoe UI',Roboto,Arial,sans-serif\"";
        $svg = "<svg class=\"local-clo-radar\" viewBox=\"0 0 $width $height\" width=\"100%\" style=\"max-width:{$width}px\" "
             . "role=\"img\" aria-label=\"" . s(get_string('radar', 'local_clo')) . "\">";
        foreach ([20, 40, 60, 80, 100] as $g) {
            $svg .= '<polygon points="' . $poly(array_fill(0, $n, $g)) . '" fill="none" stroke="#5f6368" stroke-width="1"/>';
        }
        foreach (array_values($clos) as $i => $clo) {
            [$x, $y] = $pt($i, 100);
            $svg .= "<line x1=\"$cx\" y1=\"$cy\" x2=\"$x\" y2=\"$y\" stroke=\"#5f6368\" stroke-width=\"1\"/>";
        }
        foreach ([0, 20, 40, 60, 80, 100] as $g) {
            $gy = round($cy - $r * $g / 100, 1);
            $svg .= "<text x=\"" . ($cx - 6) . "\" y=\"" . ($gy + 4) . "\" text-anchor=\"end\" font-size=\"11\" fill=\"#344054\" $font>$g</text>";
        }
        foreach (array_values($clos) as $i => $clo) {
            [$lx, $ly] = $pt($i, 100, 14);
            $anchor = abs($lx - $cx) < 10 ? 'middle' : ($lx > $cx ? 'start' : 'end');
            $lines = self::wrap($clo->code);
            $y0 = $ly + 4 - (count($lines) - 1) * (abs($lx - $cx) < 10 && $ly < $cy ? 14 : 0);
            $tspans = '';
            foreach ($lines as $k => $l) {
                $tspans .= "<tspan x=\"$lx\" dy=\"" . ($k ? 14 : 0) . "\">" . s($l) . '</tspan>';
            }
            $svg .= "<text x=\"$lx\" y=\"$y0\" text-anchor=\"$anchor\" font-size=\"13\" fill=\"#101828\" $font>$tspans</text>";
        }
        $series = [
            ['key' => 'threshold', 'color' => '#ed7d31', 'kind' => 'square', 'label' => get_string('legend_threshold', 'local_clo')],
            ['key' => 'class_avg', 'color' => '#a5a5a5', 'kind' => 'triangle', 'label' => get_string('legend_avg', 'local_clo')],
            ['key' => 'pct', 'color' => '#4472c4', 'kind' => 'diamond', 'label' => get_string('legend_me', 'local_clo')],
        ];
        $present = [];
        foreach ($series as $sdef) {
            $vals = array_map(fn($c) => isset($c->{$sdef['key']}) ? (float)$c->{$sdef['key']} : null, array_values($clos));
            if (count(array_filter($vals, fn($v) => $v !== null)) === 0) {
                continue;
            }
            $vals = array_map(fn($v) => $v ?? 0, $vals);
            $present[] = $sdef;
            $svg .= '<polygon points="' . $poly($vals) . '" fill="none" stroke="' . $sdef['color'] . '" stroke-width="'
                  . ($sdef['key'] === 'pct' ? 2.5 : 2) . '"/>';
            foreach ($vals as $i => $v) {
                [$x, $y] = $pt($i, $v);
                $svg .= self::marker($sdef['kind'], $x, $y, $sdef['color']);
            }
        }
        $lx = $cx + $r + 130;
        $ly = $cy - 24;
        foreach (array_reverse($present) as $k => $sdef) {
            $y = $ly + $k * 26;
            $svg .= "<line x1=\"$lx\" y1=\"$y\" x2=\"" . ($lx + 30) . "\" y2=\"$y\" stroke=\"{$sdef['color']}\" stroke-width=\"2\"/>";
            $svg .= self::marker($sdef['kind'], $lx + 15, $y, $sdef['color']);
            $svg .= "<text x=\"" . ($lx + 40) . "\" y=\"" . ($y + 4) . "\" font-size=\"13\" fill=\"#101828\" $font>" . s($sdef['label']) . '</text>';
        }
        return $svg . '</svg>';
    }
}
