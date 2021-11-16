import { IEzbids, IEvents, IBIDSEvent } from './store'
//import { parseEvents } from './libUnsafe'

export function createEventsTSV(ezbids : IEzbids, events : IEvents) {
    ezbids.objects.forEach(object=>{
        object.items.filter(i=>!!i.events).forEach(item=>{
            function fixUnit(v: any, unit: any) {
                switch(unit) {
                case "ms": return v/1000;
                case "us": return v/1000000;
                default:
                    return Number(v);
                }
            }

            item.eventsBIDS = [];

            //emit all values
            item.events.forEach((event: any)=>{
                
                // @ts-ignore
                let onset = fixUnit(event[events.columns.onset], events.columns.onsetUnit);

                //compute duration
                let duration = null;
                switch(events.columns.durationLogic) {
                case "add":
                    // @ts-ignore
                    duration = parseFloat(event[events.columns.duration]) + parseFloat(event[events.columns.duration2]);
                    break;
                case "subtract":
                    // @ts-ignore
                    duration = parseFloat(event[events.columns.duration]) - parseFloat(event[events.columns.duration2]);
                    console.log(event, events.columns.duration, events.columns.duration2);
                    break;
                default:
                    // @ts-ignore
                    duration = parseFloat(event[events.columns.duration]);
                }
                duration = fixUnit(duration, events.columns.durationUnit)
                const rec : IBIDSEvent = {
                    onset,
                    duration,
                };

                //rest is optional
                if(events.columns.sample) rec.sample = event[events.columns.sample];
                if(events.columns.trialType) rec.trial_type = event[events.columns.trialType];
                if(events.columns.responseTime) rec.response_time = fixUnit(event[events.columns.responseTime], events.columns.responseTimeUnit);
                if(events.columns.value) rec.value = event[events.columns.value];
                if(events.columns.HED) rec.HEAD = event[events.columns.HED];

                (item.eventsBIDS as IBIDSEvent[]).push(rec);
            });
        });
    });

}