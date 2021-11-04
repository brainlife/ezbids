import { IEzbids, IEvents, IBIDSEvent } from './store'
//import { parseEvents } from './libUnsafe'

export function createEventsTSV(ezbids : IEzbids, events : IEvents) {
    ezbids.objects.forEach(object=>{
        object.items.filter(i=>!!i.events).forEach(item=>{
            //const sidecar = object.items.find(o=>o.name == "json");
            //item.eventsBIDS = [];
            console.log("handling events")

            //compose headers
            /*
            const columns = events.columns
            const headers = [];
            if(columns.onset) headers.push("onset");
            if(columns.duration) headers.push("duration");
            if(columns.sample) headers.push("sample");
            if(columns.trialType) headers.push("trial_type");
            if(columns.responseTime) headers.push("response_time");
            if(columns.value) headers.push("value");
            if(columns.HED) headers.push("HED");
            tsv.content = headers.join(",")+"\n";

            */

            function fixUnit(v: any, unit: any) {
                switch(unit) {
                case "ms": return (v/1000);//.toFixed(3);
                default:
                    return Number(v);//.toFixed(3);
                }
            }

            item.eventsBIDS = [];

            //emit all values
            item.events.forEach((event: any)=>{
                const rec : IBIDSEvent = {
                    onset: null,
                    duration: null,
                };
                if(events.columns.onset) rec.onset = fixUnit(event[events.columns.onset], events.columns.onsetUnit);
                if(events.columns.duration) rec.duration = fixUnit(event[events.columns.duration], events.columns.durationUnit);
                if(events.columns.sample) rec.sample = event[events.columns.sample];
                if(events.columns.trialType) rec.trial_type = event[events.columns.trialType];
                if(events.columns.responseTime) rec.response_time = fixUnit(event[events.columns.responseTime], events.columns.responseTimeUnit);
                if(events.columns.value) rec.value = event[events.columns.value];
                if(events.columns.HED) rec.HEAD = event[events.columns.HED];
                //tsv.content += values.join(",")+"\n";
                // tsv.content += values.map(v=>(v|'empty')).join("\t\t")+"\n"; //causes error
                item.eventsBIDS.push(rec);
            });


            //item.eventsBIDS = parseEvents(tsv.content, ",")
        });
    });

}