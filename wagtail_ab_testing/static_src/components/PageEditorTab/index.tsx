import React, { FunctionComponent } from 'react';
import ReactDOM from 'react-dom';

interface AbTest {
    id: number;
    name: string;
    started_at: string;
    status: string;
    results_url: string;
}

interface PageEditorTabProps {
    tests: AbTest[];
    can_create_abtest: boolean;
}

const PageEditorTab: FunctionComponent<PageEditorTabProps> = ({
    tests,
    can_create_abtest
}) => {
    const noPermissionMessage = (
        <p className="help-block help-info">
            {gettext(
                'You do not have permission to create A/B tests. Please contact an administrator if you need to create one.'
            )}
        </p>
    );

    if (tests.length > 0) {
        return (
            <div className="nice-padding">
                {!can_create_abtest && noPermissionMessage}
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
                                <td>
                                    <a href={test.results_url}>{test.name}</a>
                                </td>
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
    } else {
        if (can_create_abtest) {
            return (
                <div className="nice-padding">
                    <p className="help-block help-info">
                        {gettext('To create an A/B test:')}
                        <ol>
                            <li style={{ listStyleType: 'decimal' }}>
                                {gettext(
                                    'Ensure you have a published version of the page (this will act as the "Control" in your test)'
                                )}
                            </li>
                            <li style={{ listStyleType: 'decimal' }}>
                                {gettext(
                                    'Make changes to the page content (this will act as the "Variant" in your test) and choose "SAVE AND CREATE A/B TEST"'
                                )}
                            </li>
                            <li style={{ listStyleType: 'decimal' }}>
                                {gettext('Choose your goal')}
                            </li>
                            <li style={{ listStyleType: 'decimal' }}>
                                {gettext('Watch your test results come in')}
                            </li>
                        </ol>
                    </p>
                </div>
            );
        } else {
            return <div className="nice-padding">{noPermissionMessage}</div>;
        }
    }
};

export function initPageEditorTab(element: HTMLElement, props: any) {
    ReactDOM.render(<PageEditorTab {...props} />, element);
}
