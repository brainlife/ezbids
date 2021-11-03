import { IEzbids, IEvents } from './store'

export function createEventsTSV(ezbids : IEzbids, events : IEvents) {
    console.log("TODO createEventsTSV");

    ezbids.objects.forEach(object=>{
        object.items.filter(i=>!!i.events).forEach(item=>{
            item.eventsTSV = "hello";
        });
    });
    //find event objects in ezbids.objects, then for each object, use item.event
    //to construct the event.tsv and store it as part of item
    /*
            //we handle events a bit differently.. we need to generate events.tsv from items content
            const tsv = o.items.find(o=>!!o.events);
            const sidecar = o.items.find(o=>o.name == "json");
            console.log("handling events");

            console.log("tsv");
            console.dir(tsv);
            console.log("sidecar");
            console.dir(sidecar);
            console.log("info.events");
            console.dir(info.events);

            const columns = info.events.columns;

            //compose headers
            const headers = [];
            if(columns.onset) headers.push("onset");
            if(columns.duration) headers.push("duration");
            if(columns.sample) headers.push("sample");
            if(columns.trialType) headers.push("trial_type");
            if(columns.responseTime) headers.push("response_time");
            if(columns.value) headers.push("value"); //??
            if(columns.HED) headers.push("HED");
            tsv.content = headers.join("\t")+"\n";

            function fixUnit(v, unit) {
                switch(unit) {
                case "ms": return v/1000;
                case "us": return v/1000000;
                default:
                    return v;
                }
            }

            //emit all values
            tsv.events.forEach(event=>{
                const values = [];
                if(columns.onset) values.push(fixUnit(event[columns.onset], columns.onsetUnit));
                if(columns.duration) values.push(fixUnit(event[columns.duration], columns.durationUnit));
                if(columns.sample) values.push(event[columns.sample]);
                if(columns.trialType) values.push(event[columns.trialType]);
                if(columns.responseTime) values.push(fixUnit(event[columns.responseTime], columns.responseTimeUnit));
                if(columns.value) values.push(event[columns.value]);
                if(columns.HED) values.push(event[columns.HED]);
                tsv.content += values.join("\t")+"\n";
                tsv.content += values.map(v=>(v|'empty')).join("\t")+"\n";
            });
            console.log(tsv.content);

    */
}