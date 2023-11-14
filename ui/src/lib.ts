import { IEzbids, IEvents, IBIDSEvent } from './store'
import axios from './axios.instance';
//import { parseEvents } from './libUnsafe'

export function createEventsTSV(ezbids: IEzbids, events: IEvents) {
    ezbids.objects.forEach(object => {
        object.items.filter(i => !!i.events).forEach(item => {
            function fixUnit(v: any, unit: any) {
                switch (unit) {
                    case "ms": return v / 1000;
                    case "us": return v / 1000000;
                    default:
                        return Number(v);
                }
            }

            item.eventsBIDS = [];

            //emit all values
            item.events.forEach((event: any) => {

                //compute onset
                let onset = null;
                switch (events.columns.onsetLogic) {
                    case "add":
                        // @ts-ignore
                        onset = parseFloat(event[events.columns.onset]) + parseFloat(event[events.columns.onset2]);
                        break;
                    case "subtract":
                        // @ts-ignore
                        onset = parseFloat(event[events.columns.onset]) - parseFloat(event[events.columns.onset2]);
                        break;
                    default:
                        // @ts-ignore
                        onset = parseFloat(event[events.columns.onset]);
                }
                onset = fixUnit(onset, events.columns.onsetUnit);

                //compute duration
                let duration = null;
                switch (events.columns.durationLogic) {
                    case "add":
                        // @ts-ignore
                        duration = parseFloat(event[events.columns.duration]) + parseFloat(event[events.columns.duration2]);
                        break;
                    case "subtract":
                        // @ts-ignore
                        duration = parseFloat(event[events.columns.duration]) - parseFloat(event[events.columns.duration2]);
                        break;
                    default:
                        // @ts-ignore
                        duration = parseFloat(event[events.columns.duration]);
                }
                duration = fixUnit(duration, events.columns.durationUnit);

                const rec: IBIDSEvent = {
                    onset,
                    duration,
                };

                //rest is optional
                if (events.columns.sample) {
                    switch (events.columns.sampleLogic) {
                        case "add":
                            // @ts-ignore
                            rec.sample = parseFloat(event[events.columns.sample]) + parseFloat(event[events.columns.sample2]);
                            break;
                        case "subtract":
                            // @ts-ignore
                            rec.sample = parseFloat(event[events.columns.sample]) - parseFloat(event[events.columns.sample2]);
                            break;
                        default:
                            rec.sample = parseFloat(event[events.columns.sample]);
                    }
                }
                if (events.columns.responseTime) {
                    let responseTime = null;
                    switch (events.columns.responseTimeLogic) {
                        case "add":
                            // @ts-ignore
                            responseTime = parseFloat(event[events.columns.responseTime]) + parseFloat(event[events.columns.responseTime2]);
                            break;
                        case "subtract":
                            // @ts-ignore
                            responseTime = parseFloat(event[events.columns.responseTime]) - parseFloat(event[events.columns.responseTime2]);
                            break;
                        default:
                            // @ts-ignore
                            responseTime = parseFloat(event[events.columns.responseTime]);
                    }
                    rec.response_time = fixUnit(responseTime, events.columns.responseTimeUnit);
                }

                if (events.columns.trialType) rec.trial_type = event[events.columns.trialType];
                if (events.columns.value) rec.value = event[events.columns.value];
                if (events.columns.HED) rec.HED = event[events.columns.HED];
                if (events.columns.stim_file) rec.stim_file = event[events.columns.stim_file];

                (item.eventsBIDS as IBIDSEvent[]).push(rec);

            });
        });
    });

}

export function hasJWT() {
    return !!retrieveJWT();
}

export function retrieveJWT() {
    return localStorage.getItem('jwt')
}