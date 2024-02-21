import c3 from 'c3';

import { initGoalSelector } from './components/GoalSelector';
import { initPageEditorTab } from './components/PageEditorTab';
import './style/progress.scss';

import './styles/sections.scss';

document.addEventListener('DOMContentLoaded', () => {
    // Goal selector on create new A/B test
    initGoalSelector();

    const colorControl = '#0C0073'; // CSS $color-control
    const colorControlDark = '#00B0B1'; // Wagtail --w-color-secondary-100
    const colorVariant = '#EF746F'; // CSS $color-variant

    // Match chart pattern colors to dark/light mode
    let pattern = [colorControl, colorVariant];
    if (
        window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches
    ) {
        // dark mode
        pattern = [colorControlDark, colorVariant];
    }

    // Charts on A/B test progress
    document.querySelectorAll('[component="chart"]').forEach((chartElement) => {
        if (
            !(chartElement instanceof HTMLElement) ||
            !chartElement.getAttribute('data')
        ) {
            return;
        }

        const chart = c3.generate({
            bindto: chartElement,
            data: JSON.parse(chartElement.getAttribute('data')!),
            padding: {
                right: 20,
            },
            axis: {
                x: {
                    type: 'timeseries',
                    tick: {
                        format: '%Y-%m-%d',
                    },
                },
            },
            color: {
                pattern: pattern,
            },
        });

        // Add an event listener to update chart colors when the color scheme changes
        window
            .matchMedia('(prefers-color-scheme: dark)')
            .addEventListener('change', (event) => {
                const newColorScheme = event.matches ? 'dark' : 'light';
                if (newColorScheme === 'dark') {
                    chart.data.colors({
                        Control: colorControlDark,
                        Variant: colorVariant,
                    });
                } else {
                    chart.data.colors({
                        Control: colorControl,
                        Variant: colorVariant,
                    });
                }
            });
    });

    // A/B testing tab on page editor
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
