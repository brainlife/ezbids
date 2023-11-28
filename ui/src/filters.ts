// @ts-ignore
import numeral from 'numeral';

export function formatNumber(v: number) {
    return numeral(v).format('0,0'); // displaying other groupings/separators is possi  ble, look at the docs
}

export function prettyBytes(v: number) {
    /*
    // jacked from: https://github.com/sindresorhus/pretty-bytes     
    if (typeof v !== 'number' || isNaN(v)) {     
      throw new TypeError('Expected a number');    
    } 
    */

    var unit;
    var neg = v < 0;
    var units = ['B', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

    if (neg) {
        v = -v;
    }

    if (v < 1) {
        return (neg ? '-' : '') + v + ' B';
    }

    const exponent = Math.min(Math.floor(Math.log(v) / Math.log(1000)), units.length - 1);
    v = v / Math.pow(1000, exponent);
    unit = units[exponent];
    return (neg ? '-' : '') + v.toFixed(2) + ' ' + unit;
}
