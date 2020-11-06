import React, { FunctionComponent, useEffect } from 'react';
import ReactDOM from 'react-dom';
import styled from 'styled-components';

// A label element without Wagtail's 'float: left;' rule applied
const SunkenLabel = styled.label`
    float: unset;
    width: unset;
`;

interface PageAPI {
    id: number;
    meta: {
        type: string;
    };
    title: string;
}

interface GoalPageSelectorProps {
    testPageId: number;
    onChangeSelectedPage(pageInfo: PageAPI | null): void;
}

const GoalPageSelector: FunctionComponent<GoalPageSelectorProps> = ({
    testPageId,
    onChangeSelectedPage
}) => {
    const [selectedPageId, setSelectedPageId] = React.useState<number | null>(
        null
    );
    const [
        selectedPageInfo,
        setSelectedPageInfo
    ] = React.useState<PageAPI | null>(null);

    // Fetch info about the page whenever the selected page ID is changed
    useEffect(() => {
        if (selectedPageId) {
            fetch(
                `${wagtailConfig.ADMIN_ROOT_URL}api/main/pages/${selectedPageId}/`
            )
                .then(response => response.json())
                .then(setSelectedPageInfo);
        } else {
            setSelectedPageInfo(null);
        }
    }, [selectedPageId]);

    // When we fetch new page info, run a callback so the 'Goal event' select box can update
    useEffect(() => {
        onChangeSelectedPage(selectedPageInfo);
    }, [selectedPageInfo]);

    const onChangeSelectCurrentPage = (
        e: React.ChangeEvent<HTMLInputElement>
    ) => {
        if (e.target.checked) {
            setSelectedPageId(testPageId);
        } else {
            setSelectedPageId(null);
        }
    };

    const onClickChooseDifferentPage = (
        e: React.MouseEvent<HTMLButtonElement>
    ) => {
        e.preventDefault();
        (window as any).ModalWorkflow({
            url: (window as any).chooserUrls.pageChooser,
            onload: (window as any).PAGE_CHOOSER_MODAL_ONLOAD_HANDLERS,
            responses: {
                pageChosen: function(pageData: any) {
                    setSelectedPageId(pageData.id);
                }
            }
        });
    };

    return (
        <div>
            <SunkenLabel>
                <input
                    type="checkbox"
                    onChange={onChangeSelectCurrentPage}
                    checked={selectedPageId === testPageId}
                />{' '}
                {gettext('The goal is on this page')}
            </SunkenLabel>
            <button
                className="button button-primary"
                onClick={onClickChooseDifferentPage}
            >
                {gettext('Choose a different page')}
            </button>
            {selectedPageInfo && (
                <p>
                    <b>{gettext('Selected page:')}</b> {selectedPageInfo.title}
                </p>
            )}
            <input
                type="hidden"
                name="goal_page"
                value={selectedPageId || ''}
            />
        </div>
    );
};

interface GoalSelectorProps {
    testPageId: number;
    goalTypesByPageType: {
        [pageType: string]: {
            slug: string;
            name: string;
        }[];
    };
}

const GoalSelector: FunctionComponent<GoalSelectorProps> = ({
    testPageId,
    goalTypesByPageType
}) => {
    const [selectedPageType, setSelectedPageType] = React.useState<
        string | null
    >(null);

    const onChangeSelectedPage = (pageInfo: PageAPI | null) => {
        if (pageInfo) {
            setSelectedPageType(pageInfo.meta.type);
        } else {
            setSelectedPageType(null);
        }
    };

    const goalTypes = selectedPageType
        ? goalTypesByPageType[selectedPageType.toLowerCase()] || []
        : [];

    return (
        <div>
            <SunkenLabel>{gettext('Goal page')}</SunkenLabel>
            <p>{gettext('Which page is the conversion goal on?')}</p>
            <GoalPageSelector
                testPageId={testPageId}
                onChangeSelectedPage={onChangeSelectedPage}
            />
            <SunkenLabel>{gettext('Goal event')}</SunkenLabel>
            <p>{gettext('What is the conversion event?')}</p>
            <select name="goal_event" disabled={goalTypes.length === 0}>
                {goalTypes.map(({ slug, name }) => (
                    <option key={slug} value={slug}>
                        {name}
                    </option>
                ))}
            </select>
        </div>
    );
};

export function initGoalSelector() {
    document
        .querySelectorAll('div[data-component="goal-selector"]')
        .forEach((element: HTMLDivElement) => {
            if (!element.dataset.props) {
                return;
            }

            ReactDOM.render(
                <GoalSelector {...JSON.parse(element.dataset.props)} />,
                element
            );
        });
}
