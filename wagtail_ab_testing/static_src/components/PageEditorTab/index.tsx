import React, { FunctionComponent } from 'react';
import ReactDOM from 'react-dom';

interface AbTest {
    id: number;
    name: string;
    started_at: string;
    status: string;
}

interface PageEditorTabProps {
    tests: AbTest[];
}

const PageEditorTab: FunctionComponent<PageEditorTabProps> = ({ tests }) => {
    return (
        <div className="nice-padding">
            <table className="listing">
                <thead>
                    <tr>
                        <th className="title">{gettext('Started at')}</th>
                        <th>{gettext('Test name')}</th>
                        <th>{gettext('Status')}</th>
                    </tr>
                </thead>
                <tbody>
                    {tests.map(test => (
                        <tr key={test.id}>
                            <td className="title">{test.started_at}</td>
                            <td>{test.name}</td>
                            <td>
                                <span className="status-tag primary">
                                    {test.status}
                                </span>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export function initPageEditorTab(element: HTMLElement, props: any) {
    ReactDOM.render(<PageEditorTab {...props} />, element);
}
