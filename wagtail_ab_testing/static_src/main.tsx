import c3 from 'c3';

import { initGoalSelector } from './components/GoalSelector';
import { initPageEditorTab } from './components/PageEditorTab';
import './style/progress.scss';

import './styles/sections.scss';

document.addEventListener('DOMContentLoaded', () => {
    // Goal selector on create new A/B test
    initGoalSelector();

    // Charts on A/B test progress
    document.querySelectorAll('[component="chart"]').forEach(chartElement => {
        if (
            !(chartElement instanceof HTMLElement) ||
            !chartElement.getAttribute('data')
        ) {
            return;
        }

        c3.generate({
            bindto: chartElement,
            data: JSON.parse(chartElement.getAttribute('data')!),
            padding: {
                right: 20
            },
            axis: {
                x: {
                    type: 'timeseries',
                    tick: {
                        format: '%Y-%m-%d'
                    }
                }
            },
            color: {
                pattern: ['#0C0073', '#EF746F']
            }
        });
    });

    // A/B testing tab on page edito
    if (abTestingTabProps) {
        $('ul.tab-nav').append(`<li role="tab" aria-controls="tab-abtesting">
            <a href="#tab-abtesting" class="">${gettext('A/B testing')}</a>
        </li>`);
        $('div.tab-content').append(`
            <section id="tab-abtesting" role="tabpanel" aria-labelledby="tab-label-abtesting">
            </section>
        `);

        const abTestingTab = document.getElementById('tab-abtesting');
        if (abTestingTab) {
            initPageEditorTab(abTestingTab, abTestingTabProps);
        }
    }
});
