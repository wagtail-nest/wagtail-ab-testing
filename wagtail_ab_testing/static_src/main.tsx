import c3 from 'c3';

import { initGoalSelector } from './components/GoalSelector';
import './style/progress.scss';

document.addEventListener('DOMContentLoaded', () => {
    initGoalSelector();

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
});
