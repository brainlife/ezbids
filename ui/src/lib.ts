import { IEzbids, IEvents } from './store'

export function createEventsTSV(ezbids : IEzbids, events : IEvents) {
    ezbids.objects.forEach(object=>{
        object.items.filter(i=>!!i.events).forEach(item=>{
            const tsv = item.events
            const sidecar = object.items.find(o=>o.name == "json");
            item.eventsTSV = "hello";
            console.log("handling events")

            const columns = events.columns
            //compose headers
            const headers = [];
            if(columns.onset) headers.push("onset");
            if(columns.duration) headers.push("duration");
            if(columns.sample) headers.push("sample");
            if(columns.trialType) headers.push("trial_type");
            if(columns.responseTime) headers.push("response_time");
            if(columns.value) headers.push("value");
            if(columns.HED) headers.push("HED");
            tsv.content = headers.join("\t\t")+"\n";

            function fixUnit(v: any, unit: any) {
                switch(unit) {
                case "ms": return (v/1000).toFixed(3);
                default:
                    return Number(v).toFixed(3);
                }
            }

            //emit all values
            tsv.forEach((event: any)=>{
                const values = [];
                if(columns.onset) values.push(fixUnit(event[columns.onset], columns.onsetUnit));
                if(columns.duration) values.push(fixUnit(event[columns.duration], columns.durationUnit));
                if(columns.sample) values.push(event[columns.sample]);
                if(columns.trialType) values.push(event[columns.trialType]);
                if(columns.responseTime) values.push(fixUnit(event[columns.responseTime], columns.responseTimeUnit));
                if(columns.value) values.push(event[columns.value]);
                if(columns.HED) values.push(event[columns.HED]);
                tsv.content += values.join("\t\t")+"\n";
                tsv.content += values.map(v=>(v|'empty')).join("\t\t")+"\n";
            });

            item.eventsTSV = tsv.content

        });
    });
}