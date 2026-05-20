<template>
    <div class="objects-page">
        <ObjectsIntro />

        <div class="objects-workspace">
            <aside class="objects-list-panel">
                <ObjectsListPane
                    ref="listPane"
                    :organized="ezbids._organized"
                    :selected-object="so"
                    @select="select"
                    @exclude-subject="excludeSubject"
                    @exclude-session="excludeSession"
                />
            </aside>

            <main class="objects-detail-panel">
                <ObjectsEmptyState v-if="!so" />

                <ObjectsEditorPanel
                    v-if="so && sess"
                    :object="so"
                    :session="sess"
                    @update="update"
                    @niivue="$emit('niivue', $event)"
                    @form-submitted="submitForm"
                />
            </main>
        </div>
    </div>
</template>

<script lang="ts">
import { mapState, mapGetters } from 'vuex';
import { defineComponent } from 'vue';
import { IObject, OrganizedSession, OrganizedSubject, Session } from '@/store/store.types';
import ObjectsIntro from './ObjectsIntro.vue';
import ObjectsListPane from './ObjectsListPane.vue';
import ObjectsEmptyState from './ObjectsEmptyState.vue';
import ObjectsEditorPanel from './ObjectsEditorPanel.vue';
import { validateObject, validateAllObjects, type ObjectsValidationContext } from './objectsValidation';
export default defineComponent({
    components: {
        ObjectsIntro,
        ObjectsListPane,
        ObjectsEmptyState,
        ObjectsEditorPanel,
    },
    emits: ['niivue', 'mapObjects', 'updateObject'],

    data() {
        return {
            so: null as IObject | null,
            sess: null as OrganizedSession | null,
        };
    },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema', 'events']),
        ...mapGetters(['getBIDSEntities', 'findSubject', 'findSession', 'findSubjectFromString']),

        totalIssues() {
            let count = 0;
            this.ezbids.objects.forEach((o: IObject) => {
                if (this.isExcluded(o)) return;
                count += o.validationErrors.length;
            });
            return count;
        },

        validationContext(): ObjectsValidationContext {
            return {
                ezbids: this.ezbids,
                getBIDSEntities: this.getBIDSEntities,
                isExcluded: this.isExcluded,
            };
        },
    },

    mounted() {
        this.validateAll();
    },

    methods: {
        findSessionFromString(sub: string, ses: string) {
            const subject = this.findSubjectFromString(sub);
            return subject.sessions.find((s: Session) => s.session == ses);
        },

        excludeSubject(sub: string, b: boolean) {
            if (this.findSubjectFromString(sub) !== undefined) {
                const subject = this.findSubjectFromString(sub);
                subject.exclude = b;
            } else {
                const o_subs = this.ezbids._organized.filter((e: OrganizedSubject) => e.sub == sub);
                o_subs.forEach((o_sub: OrganizedSubject) => {
                    o_sub.sess.forEach((ses) => {
                        ses.objects.forEach((obj) => {
                            obj.exclude = b;
                        });
                    });
                });
            }

            this.$emit('mapObjects');
            this.validateAll();
        },

        isExcluded(o: IObject) {
            if (o.exclude) {
                return true;
            } else if (o._exclude) {
                return true;
            } else if (o._type === 'exclude') {
                return true;
            } else {
                return false;
            }
        },

        excludeSession(sub: string, ses: string, b: boolean) {
            if (this.findSubjectFromString(sub) !== undefined && this.findSessionFromString(sub, ses) !== undefined) {
                const session = this.findSessionFromString(sub, ses);
                if (session) session.exclude = b;
            } else {
                const o_subs = this.ezbids._organized.filter((e: OrganizedSubject) => e.sub == sub);
                o_subs.forEach((o_sub: OrganizedSubject) => {
                    const o_ses = o_sub.sess.filter((s) => s.sess == ses);
                    o_ses.forEach((ses) => {
                        ses.objects.forEach((obj) => {
                            obj.exclude = b;
                        });
                    });
                });
            }

            this.$emit('mapObjects');
            this.validateAll();
        },

        select(o: IObject, sess: OrganizedSession) {
            this.sess = sess;
            this.so = o;
            this.scrollSelectedObjectIntoView();
        },

        scrollSelectedObjectIntoView(behavior: ScrollBehavior = 'smooth') {
            if (!this.so) return;
            const listPane = this.$refs.listPane as InstanceType<typeof ObjectsListPane> | undefined;
            listPane?.scrollSelectedIntoView(this.so.idx, behavior);
        },

        update(o: IObject | null) {
            if (!o) return;
            this.$emit('updateObject', o);
            this.scrollSelectedObjectIntoView('smooth');
        },

        isValid(cb: (err?: string) => void) {
            this.$emit('mapObjects');
            this.validateAll();

            let err = undefined;
            this.ezbids.objects.forEach((o: IObject) => {
                if (o.validationErrors.length > 0) err = 'Please correct all issues.';
            });

            const one = this.ezbids.objects.find((o: IObject) => !o._exclude);
            if (!one) {
                err = 'All objects are excluded. Please update so that there is at least 1 object to output to BIDS';
            }

            return cb(err);
        },

        validate(o: IObject | null) {
            validateObject(this.validationContext, o);
        },

        validateAll() {
            validateAllObjects(this.validationContext);
        },

        submitForm(data: any) {
            this.ezbids = data;
        },
    },
});
</script>

<style lang="scss" scoped>
.objects-page {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
    padding: 0.5rem 1.25rem 1rem;
    min-height: calc(100vh - 10rem);
}

.objects-workspace {
    display: grid;
    grid-template-columns: minmax(240px, 30%) minmax(0, 1fr);
    gap: 12px;
    margin: 1rem 0;
    flex: 1 1 auto;
    min-height: calc(100vh - 22rem);
    min-width: 0;
}

.objects-workspace > * {
    min-height: 0;
}

.objects-list-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    min-width: 0;
    border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
    padding-right: 8px;
}

.objects-detail-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    min-width: 0;
    padding-left: 4px;
    overflow-x: hidden;
    overflow-y: auto;
}
</style>
